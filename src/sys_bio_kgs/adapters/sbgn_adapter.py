"""
SBGN Adapter

This adapter handles SBGN (Systems Biology Graphical Notation) XML files
using the momapy library to parse and extract nodes and edges for BioCypher.
"""

import logging
import hashlib
from pathlib import Path
from typing import Iterator, Tuple, Dict, Any, Optional
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Lazy import of momapy to avoid import errors if system dependencies are missing
_SBGNMLReader = None
_ReaderResult = None
_MOMAPY_AVAILABLE = False


def _import_momapy():
    """Lazy import of momapy modules."""
    global _SBGNMLReader, _ReaderResult, _MOMAPY_AVAILABLE
    if _SBGNMLReader is None:
        try:
            from momapy.sbgn.io.sbgnml import _SBGNMLReader as Reader
            from momapy.io import ReaderResult as Result
            _SBGNMLReader = Reader
            _ReaderResult = Result
            _MOMAPY_AVAILABLE = True
        except ImportError as e:
            logger.warning(
                f"momapy not available (system dependencies may be missing): {e}. "
                "Falling back to direct XML parsing."
            )
            _MOMAPY_AVAILABLE = False
    return _SBGNMLReader, _ReaderResult, _MOMAPY_AVAILABLE


class SBGNAdapter:
    """
    Adapter for SBGN XML data source.
    
    This adapter implements the BioCypher adapter interface for SBGN files,
    extracting biological entities (glyphs) as nodes and interactions (arcs) as edges.
    """

    # Mapping of SBGN glyph classes to BioCypher node types (using SBO class names)
    GLYPH_CLASS_TO_NODE_TYPE = {
        "macromolecule": "macromolecule",  # SBO_0000245: macromolecule
        "nucleic acid feature": "information macromolecule",  # SBO_0000246: information macromolecule
        "simple chemical": "simple chemical",  # SBO_0000247: simple chemical
        "process": "process",  # SBO_0000375: process
        "source and sink": "sink reaction",  # SBO_0000632: sink reaction
        "compartment": "compartment",
        "phenotype": "phenotype",
        "perturbation": "perturbation",
    }

    # Mapping of SBGN arc classes to BioCypher edge types (using SBO class names where applicable)
    ARC_CLASS_TO_EDGE_TYPE = {
        "consumption": "consumption",  # Links to SBO_0000010: reactant via is_a
        "production": "production",  # Links to SBO_0000011: product via is_a
        "inhibition": "inhibition",  # SBO_0000169: inhibition
        "necessary stimulation": "necessary_stimulation",  # SBO_0000171: necessary stimulation
        "catalysis": "catalysis",  # SBO_0000172: catalysis
        "modulation": "modifier",  # SBO_0000019: modifier
        "stimulation": "stimulation",  # SBO_0000170: stimulation
        "equivalence arc": "equivalence",
    }

    def __init__(self, data_source: str | Path, **kwargs):
        """
        Initialize the SBGN adapter.

        Args:
            data_source: Path to the SBGN XML file
            **kwargs: Additional configuration parameters
        """
        self.data_source = Path(data_source)
        self.config = kwargs
        self.sbgn_map: Optional[Any] = None

        if not self.data_source.exists():
            raise FileNotFoundError(f"SBGN file not found: {self.data_source}")

        logger.info(f"Initialized SBGNAdapter with data source: {self.data_source}")

    def _load_sbgn_map(self) -> Any:
        """Load and parse the SBGN file using momapy or fallback XML parser."""
        if self.sbgn_map is None:
            logger.info(f"Loading SBGN file: {self.data_source}")
            Reader, _, momapy_available = _import_momapy()
            
            if momapy_available:
                # Use momapy if available
                result = Reader.read(self.data_source)
                if not hasattr(result, "obj") or result.obj is None:
                    raise ValueError(f"Failed to parse SBGN file: {self.data_source}")
                self.sbgn_map = result.obj
            else:
                # Fallback to direct XML parsing
                logger.info("Using fallback XML parser")
                self.sbgn_map = self._parse_xml_directly()
            
            logger.info("SBGN file loaded successfully")
        return self.sbgn_map
    
    def _parse_xml_directly(self) -> Dict[str, Any]:
        """Parse SBGN XML directly using ElementTree as fallback."""
        tree = ET.parse(self.data_source)
        root = tree.getroot()
        
        # SBGN namespace
        ns = {"sbgn": "http://sbgn.org/libsbgn/0.2"}
        
        # Parse glyphs - only top-level glyphs (not nested ones)
        # Find the map element first
        map_elem = root.find(".//sbgn:map", ns)
        if map_elem is None:
            map_elem = root
        
        glyphs = []
        # Only get direct children glyphs of the map, not nested glyphs
        for glyph_elem in map_elem.findall("sbgn:glyph", ns):
            glyph = {
                "id": glyph_elem.get("id"),
                "class": glyph_elem.get("class", "unknown"),
                "orientation": glyph_elem.get("orientation"),
            }
            
            # Get label
            label_elem = glyph_elem.find("sbgn:label", ns)
            if label_elem is not None:
                glyph["label"] = label_elem.get("text", "")
            
            # Get bbox
            bbox_elem = glyph_elem.find("sbgn:bbox", ns)
            if bbox_elem is not None:
                glyph["bbox"] = {
                    "x": float(bbox_elem.get("x", 0)),
                    "y": float(bbox_elem.get("y", 0)),
                    "w": float(bbox_elem.get("w", 0)),
                    "h": float(bbox_elem.get("h", 0)),
                }
            
            # Get ports
            ports = []
            for port_elem in glyph_elem.findall("sbgn:port", ns):
                ports.append({
                    "id": port_elem.get("id"),
                    "x": float(port_elem.get("x", 0)),
                    "y": float(port_elem.get("y", 0)),
                })
            if ports:
                glyph["ports"] = ports
            
            # Get nested glyphs (e.g., unit of information) - but don't add them as separate nodes
            nested_glyphs = []
            for nested in glyph_elem.findall("sbgn:glyph", ns):
                nested_glyph = {
                    "id": nested.get("id"),
                    "class": nested.get("class", "unknown"),
                }
                nested_label = nested.find("sbgn:label", ns)
                if nested_label is not None:
                    nested_glyph["label"] = nested_label.get("text", "")
                nested_glyphs.append(nested_glyph)
            if nested_glyphs:
                glyph["nested_glyphs"] = nested_glyphs
            
            glyphs.append(glyph)
        
        # Parse arcs
        arcs = []
        for arc_elem in root.findall(".//sbgn:arc", ns):
            arc = {
                "id": arc_elem.get("id"),
                "class": arc_elem.get("class", "unknown"),
                "source": arc_elem.get("source"),
                "target": arc_elem.get("target"),
            }
            
            # Get start/end points
            start_elem = arc_elem.find("sbgn:start", ns)
            if start_elem is not None:
                arc["start"] = {
                    "x": float(start_elem.get("x", 0)),
                    "y": float(start_elem.get("y", 0)),
                }
            
            end_elem = arc_elem.find("sbgn:end", ns)
            if end_elem is not None:
                arc["end"] = {
                    "x": float(end_elem.get("x", 0)),
                    "y": float(end_elem.get("y", 0)),
                }
            
            # Get intermediate points
            next_points = []
            next_elem = arc_elem.find("sbgn:next", ns)
            while next_elem is not None:
                next_points.append({
                    "x": float(next_elem.get("x", 0)),
                    "y": float(next_elem.get("y", 0)),
                })
                next_elem = next_elem.find("sbgn:next", ns)
            if next_points:
                arc["next_points"] = next_points
            
            arcs.append(arc)
        
        return {
            "glyphs": glyphs,
            "arcs": arcs,
            "language": root.find(".//sbgn:map", ns).get("language", "") if root.find(".//sbgn:map", ns) is not None else "",
        }

    def _get_glyph_label(self, glyph) -> Optional[str]:
        """Extract label text from a glyph."""
        if hasattr(glyph, "label") and glyph.label:
            if hasattr(glyph.label, "text"):
                return glyph.label.text
            elif isinstance(glyph.label, str):
                return glyph.label
        return None

    def _get_glyph_class(self, glyph) -> str:
        """Extract class from a glyph, handling different attribute names."""
        if hasattr(glyph, "class_"):
            return glyph.class_
        elif hasattr(glyph, "class"):
            return getattr(glyph, "class")
        elif hasattr(glyph, "glyph_class"):
            return glyph.glyph_class
        return "unknown"

    def _get_arc_class(self, arc) -> str:
        """Extract class from an arc, handling different attribute names."""
        if isinstance(arc, dict):
            return arc.get("class", "unknown")
        else:
            if hasattr(arc, "class_"):
                return arc.class_
            elif hasattr(arc, "class"):
                return getattr(arc, "class")
            elif hasattr(arc, "arc_class"):
                return arc.arc_class
        return "unknown"

    def _resolve_arc_endpoints(self, arc) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve arc endpoints to glyph IDs.
        
        Arcs can connect to:
        - Glyphs directly (source/target are glyph IDs)
        - Ports on processes (source/target are port IDs, need to find parent glyph)
        
        Returns:
            Tuple of (source_glyph_id, target_glyph_id)
        """
        source_id = None
        target_id = None

        # Get source and target IDs
        if isinstance(arc, dict):
            source_id = arc.get("source")
            target_id = arc.get("target")
        else:
            if hasattr(arc, "source"):
                source_id = arc.source
            if hasattr(arc, "target"):
                target_id = arc.target

        if not source_id or not target_id:
            return None, None

        sbgn_map = self._load_sbgn_map()

        # Get glyphs list using the same pattern as get_nodes()
        if isinstance(sbgn_map, dict):
            glyphs = sbgn_map.get("glyphs", [])
        else:
            glyphs = []
            if hasattr(sbgn_map, "model") and hasattr(sbgn_map.model, "glyphs"):
                glyphs = sbgn_map.model.glyphs
            elif hasattr(sbgn_map, "glyphs"):
                glyphs = sbgn_map.glyphs
            elif hasattr(sbgn_map, "maps") and len(sbgn_map.maps) > 0:
                if hasattr(sbgn_map.maps[0], "glyphs"):
                    glyphs = sbgn_map.maps[0].glyphs

        # Check if source/target are ports and resolve to parent glyph
        def resolve_to_glyph(port_or_glyph_id: str) -> Optional[str]:
            """Resolve a port ID to its parent glyph ID, or return glyph ID as-is."""
            # Check if it's a port (format: glyph_id.port_number)
            if "." in port_or_glyph_id:
                # Extract glyph ID from port ID
                glyph_id = port_or_glyph_id.rsplit(".", 1)[0]
                return glyph_id

            # Check if it's a glyph ID directly
            # Try to find the glyph in the map
            for glyph in glyphs:
                glyph_id = None
                if isinstance(glyph, dict):
                    glyph_id = glyph.get("id")
                else:
                    if hasattr(glyph, "id"):
                        glyph_id = glyph.id
                    elif hasattr(glyph, "glyph_id"):
                        glyph_id = glyph.glyph_id

                if glyph_id == port_or_glyph_id:
                    return glyph_id

                # Check ports
                if isinstance(glyph, dict):
                    ports = glyph.get("ports", [])
                    for port in ports:
                        port_id = port.get("id")
                        if port_id == port_or_glyph_id:
                            return glyph_id
                else:
                    if hasattr(glyph, "ports"):
                        for port in glyph.ports:
                            port_id = None
                            if hasattr(port, "id"):
                                port_id = port.id
                            elif hasattr(port, "port_id"):
                                port_id = port.port_id

                            if port_id == port_or_glyph_id:
                                return glyph_id

            return port_or_glyph_id

        source_glyph_id = resolve_to_glyph(source_id)
        target_glyph_id = resolve_to_glyph(target_id)

        return source_glyph_id, target_glyph_id

    def get_nodes(self) -> Iterator[Tuple[str, str, Dict[str, Any]]]:
        """
        Extract nodes from the SBGN file.

        Yields:
            Tuples of (node_id, node_label, properties_dict) for each node
        """
        logger.info("Extracting nodes from SBGN file")
        sbgn_map = self._load_sbgn_map()

        # Check if we're using the XML fallback (dict structure)
        if isinstance(sbgn_map, dict):
            glyphs = sbgn_map.get("glyphs", [])
        else:
            # Access glyphs from the map (momapy structure)
            # momapy structure: sbgn_map.model.glyphs or sbgn_map.glyphs
            glyphs = []
            if hasattr(sbgn_map, "model") and hasattr(sbgn_map.model, "glyphs"):
                glyphs = sbgn_map.model.glyphs
            elif hasattr(sbgn_map, "glyphs"):
                glyphs = sbgn_map.glyphs
            elif hasattr(sbgn_map, "maps") and len(sbgn_map.maps) > 0:
                # Some SBGN files have maps as a list
                if hasattr(sbgn_map.maps[0], "glyphs"):
                    glyphs = sbgn_map.maps[0].glyphs

        node_count = 0
        for glyph in glyphs:
            # Handle both dict (XML fallback) and object (momapy) structures
            if isinstance(glyph, dict):
                # XML fallback structure
                glyph_id = glyph.get("id")
                if not glyph_id:
                    continue
                
                glyph_class = glyph.get("class", "unknown")
                label_text = glyph.get("label")
                
                # Map to BioCypher node type
                node_type = self.GLYPH_CLASS_TO_NODE_TYPE.get(
                    glyph_class, "biological_entity"
                )
                
                # Build properties
                properties: Dict[str, Any] = {
                    "sbgn_class": glyph_class,
                    "sbgn_id": glyph_id,
                }
                
                if label_text:
                    properties["name"] = label_text
                    properties["label"] = label_text
                
                # Extract bbox
                bbox = glyph.get("bbox")
                if bbox:
                    properties["x"] = bbox.get("x")
                    properties["y"] = bbox.get("y")
                    properties["width"] = bbox.get("w")
                    properties["height"] = bbox.get("h")
                
                # Extract orientation
                if glyph.get("orientation"):
                    properties["orientation"] = glyph["orientation"]
                
                # Extract unit of information from nested glyphs
                nested_glyphs = glyph.get("nested_glyphs", [])
                if nested_glyphs:
                    unit_info = []
                    for nested in nested_glyphs:
                        if nested.get("class") == "unit of information":
                            nested_label = nested.get("label")
                            if nested_label:
                                unit_info.append(nested_label)
                    if unit_info:
                        properties["unit_of_information"] = unit_info
            else:
                # momapy object structure
                # Skip nested glyphs (e.g., unit of information inside nucleic acid feature)
                # Only process top-level glyphs
                glyph_id = None
                if hasattr(glyph, "id"):
                    glyph_id = glyph.id
                elif hasattr(glyph, "glyph_id"):
                    glyph_id = glyph.glyph_id

                if not glyph_id:
                    continue

                # Get glyph class
                glyph_class = self._get_glyph_class(glyph)
                
                # Map to BioCypher node type
                node_type = self.GLYPH_CLASS_TO_NODE_TYPE.get(
                    glyph_class, "biological_entity"
                )

                # Extract label
                label_text = self._get_glyph_label(glyph)

                # Build properties
                properties: Dict[str, Any] = {
                    "sbgn_class": glyph_class,
                    "sbgn_id": glyph_id,
                }

                if label_text:
                    properties["name"] = label_text
                    properties["label"] = label_text

                # Extract bounding box information if available
                if hasattr(glyph, "bbox"):
                    bbox = glyph.bbox
                    if hasattr(bbox, "x"):
                        properties["x"] = float(bbox.x) if bbox.x is not None else None
                    if hasattr(bbox, "y"):
                        properties["y"] = float(bbox.y) if bbox.y is not None else None
                    if hasattr(bbox, "w"):
                        properties["width"] = float(bbox.w) if bbox.w is not None else None
                    if hasattr(bbox, "h"):
                        properties["height"] = float(bbox.h) if bbox.h is not None else None

                # Extract orientation if available
                if hasattr(glyph, "orientation"):
                    properties["orientation"] = glyph.orientation

                # Extract unit of information if present (for nucleic acid features)
                if hasattr(glyph, "glyphs") or hasattr(glyph, "sub_glyphs"):
                    sub_glyphs = getattr(glyph, "glyphs", None) or getattr(
                        glyph, "sub_glyphs", None
                    )
                    if sub_glyphs:
                        unit_info = []
                        for sub_glyph in sub_glyphs:
                            sub_class = self._get_glyph_class(sub_glyph)
                            if sub_class == "unit of information":
                                sub_label = self._get_glyph_label(sub_glyph)
                                if sub_label:
                                    unit_info.append(sub_label)
                        if unit_info:
                            properties["unit_of_information"] = unit_info

            yield (glyph_id, node_type, properties)
            node_count += 1

        logger.info(f"Extracted {node_count} nodes from SBGN file")

    def get_edges(self) -> Iterator[Tuple[str, str, str, str, Dict[str, Any]]]:
        """
        Extract edges from the SBGN file.

        Yields:
            Tuples of (edge_id, source_id, target_id, edge_type, properties_dict)
            for each edge
        """
        logger.info("Extracting edges from SBGN file")
        sbgn_map = self._load_sbgn_map()

        # Check if we're using the XML fallback (dict structure)
        if isinstance(sbgn_map, dict):
            arcs = sbgn_map.get("arcs", [])
        else:
            # Access arcs from the map (momapy structure)
            arcs = []
            if hasattr(sbgn_map, "model") and hasattr(sbgn_map.model, "arcs"):
                arcs = sbgn_map.model.arcs
            elif hasattr(sbgn_map, "arcs"):
                arcs = sbgn_map.arcs
            elif hasattr(sbgn_map, "maps") and len(sbgn_map.maps) > 0:
                if hasattr(sbgn_map.maps[0], "arcs"):
                    arcs = sbgn_map.maps[0].arcs

        edge_count = 0
        for arc in arcs:
            # Get arc class
            arc_class = self._get_arc_class(arc)

            # Map to BioCypher edge type
            edge_type = self.ARC_CLASS_TO_EDGE_TYPE.get(arc_class, "interaction")

            # Resolve endpoints
            source_id, target_id = self._resolve_arc_endpoints(arc)

            if not source_id or not target_id:
                arc_id = arc.get("id") if isinstance(arc, dict) else getattr(arc, "id", "unknown")
                logger.warning(
                    f"Could not resolve endpoints for arc {arc_id}"
                )
                continue

            # Get or generate edge ID
            if isinstance(arc, dict):
                edge_id = arc.get("id")
            else:
                edge_id = getattr(arc, "id", None)
            
            # If no arc ID, generate a hash from source, target, and arc class
            if not edge_id:
                edge_id_str = f"{source_id}_{target_id}_{arc_class}"
                edge_id = hashlib.md5(edge_id_str.encode()).hexdigest()[:12]

            # Build properties
            properties: Dict[str, Any] = {
                "sbgn_arc_class": arc_class,
            }

            # Handle both dict and object structures
            if isinstance(arc, dict):
                # XML fallback structure
                if arc.get("id"):
                    properties["sbgn_arc_id"] = arc["id"]
                
                # Extract start/end coordinates
                start = arc.get("start")
                if start:
                    properties["start_x"] = start.get("x")
                    properties["start_y"] = start.get("y")
                
                end = arc.get("end")
                if end:
                    properties["end_x"] = end.get("x")
                    properties["end_y"] = end.get("y")
                
                # Extract intermediate points (convert to string format for BioCypher)
                next_points = arc.get("next_points", [])
                if next_points:
                    # Convert list of dicts to string representation
                    points_str = "|".join([f"{p.get('x',0)},{p.get('y',0)}" for p in next_points])
                    properties["intermediate_points"] = points_str
            else:
                # momapy object structure
                # Extract arc ID if available
                if hasattr(arc, "id"):
                    properties["sbgn_arc_id"] = arc.id

                # Extract start/end coordinates if available
                if hasattr(arc, "start"):
                    start = arc.start
                    if hasattr(start, "x") and hasattr(start, "y"):
                        properties["start_x"] = float(start.x) if start.x is not None else None
                        properties["start_y"] = float(start.y) if start.y is not None else None

                if hasattr(arc, "end"):
                    end = arc.end
                    if hasattr(end, "x") and hasattr(end, "y"):
                        properties["end_x"] = float(end.x) if end.x is not None else None
                        properties["end_y"] = float(end.y) if end.y is not None else None

                # Extract intermediate points if available
                if hasattr(arc, "next") or hasattr(arc, "points"):
                    points = []
                    if hasattr(arc, "next"):
                        # Handle next points
                        next_point = arc.next
                        while next_point:
                            if hasattr(next_point, "x") and hasattr(next_point, "y"):
                                points.append(
                                    {
                                        "x": float(next_point.x) if next_point.x is not None else None,
                                        "y": float(next_point.y) if next_point.y is not None else None,
                                    }
                                )
                            next_point = getattr(next_point, "next", None)
                    elif hasattr(arc, "points"):
                        for point in arc.points:
                            if hasattr(point, "x") and hasattr(point, "y"):
                                points.append(
                                    {
                                        "x": float(point.x) if point.x is not None else None,
                                        "y": float(point.y) if point.y is not None else None,
                                    }
                                )
                    if points:
                        # Convert list of dicts to string representation for BioCypher
                        points_str = "|".join([f"{p.get('x',0)},{p.get('y',0)}" for p in points])
                        properties["intermediate_points"] = points_str

            yield (edge_id, source_id, target_id, edge_type, properties)
            edge_count += 1

        logger.info(f"Extracted {edge_count} edges from SBGN file")

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the data source.

        Returns:
            Dictionary containing metadata
        """
        sbgn_map = self._load_sbgn_map()
        metadata = {
            "name": "SBGNAdapter",
            "data_source": str(self.data_source),
            "data_type": "sbgn",
            "version": "0.1.0",
            "adapter_class": "SBGNAdapter",
        }

        # Extract map-level metadata if available
        if hasattr(sbgn_map, "language"):
            metadata["sbgn_language"] = sbgn_map.language
        if hasattr(sbgn_map, "maps") and len(sbgn_map.maps) > 0:
            map_obj = sbgn_map.maps[0]
            if hasattr(map_obj, "language"):
                metadata["sbgn_language"] = map_obj.language

        return metadata

    def validate_data_source(self) -> bool:
        """
        Validate that the SBGN data source is accessible and properly formatted.

        Returns:
            True if data source is valid, False otherwise
        """
        try:
            if not self.data_source.exists() or not self.data_source.is_file():
                return False

            # Try to parse the SBGN file
            Reader, _ = _import_momapy()
            result = Reader.read(self.data_source)
            return hasattr(result, "obj") and result.obj is not None

        except Exception as e:
            logger.error(f"Data source validation failed: {e}")
            return False

