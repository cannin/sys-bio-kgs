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
import momapy.sbgn.io.sbgnml
import momapy.io
logger = logging.getLogger(__name__)


class MoMaPySBGNAdapter:
    """
    Adapter for SBGN XML data source.
    
    This adapter implements the BioCypher adapter interface for SBGN files,
    extracting biological entities (glyphs) as nodes and interactions (arcs) as edges.
    """

    # Mapping of SBGN glyph classes to BioCypher node types (using SBO class names)
    GLYPH_CLASS_TO_NODE_TYPE = {
        "macromolecule": ("macromolecule", "SBO_0000245", "physical entity"),  # SBO_0000245: macromolecule
        "nucleic acid feature": ("information macromolecule", "SBO_0000246", "macromolecule"),  # SBO_0000246: information macromolecule
        "nucleicacidfeature": ("information macromolecule", "SBO_0000246", "macromolecule"),  # SBO_0000246: information macromolecule
        "simple chemical": ("simple chemical", "SBO_0000247", "physical entity"),  # SBO_0000247: simple chemical
        "process": ("process", "SBO_0000375", None),  # SBO_0000375: process
        "source and sink": ("sink reaction", "SBO_0000632", None),  # SBO_0000632: sink reaction
        "emptyset": ("empty set", "SBO_0000355", "physical entity"),  # SBO_0000355: empty set
        "compartment": ("compartment", "SBO_0000290", None),
        "physical entity": ("physical entity", "SBO_0000236", None),  # SBO_0000288: physical entity
    }

    # Mapping of SBGN arc classes to BioCypher edge types (using SBO class names where applicable)
    ARC_CLASS_TO_EDGE_TYPE = {
        "consumption": ("consumption", "SBO_0000010", "reactant"),  # Links to SBO_0000010: reactant via is_a
        "production": ("production", "SBO_0000011", "product"),  # Links to SBO_0000011: product via is_a
        "inhibition": ("inhibition", "SBO_0000169", "modifier"),  # SBO_0000169: inhibition
        "necessary stimulation": ("necessary stimulation", "SBO_0000171", "modifier"),  # SBO_0000171: necessary stimulation
        "necessarystimulation": ("necessary stimulation", "SBO_0000171", "modifier"),
        "catalysis": ("catalysis", "SBO_0000172", "modifier"),  # SBO_0000172: catalysis
        "modulation": ("modifier", "SBO_0000019", "modifier"),  # SBO_0000019: modifier
        "stimulation": ("stimulation", "SBO_0000170", "modifier"),  # SBO_0000170: stimulation
        "reactant": ("reactant", "SBO_0000010", None),  # SBO_0000010: reactant
        "product": ("product", "SBO_0000011", None),  # SBO_
        "modifier": ("modifier", "SBO_0000019", None),  # SBO_0000019: modifier
        "process": ("process", "SBO_0000375", None),  # SBO_0000375: process
    }

    def __init__(self, data_source: str | Path, add_default_compartments: bool = True, schema_manager = None, **kwargs):
        """
        Initialize the SBGN adapter.

        Args:
            data_source: Path to the SBGN XML file
            **kwargs: Additional configuration parameters
        """
        self.data_source = Path(data_source)
        
        if not self.data_source.exists():
            raise FileNotFoundError(f"SBGN file not found: {self.data_source}")
        
        self.config = kwargs
        self.sbgn_map = self._load_sbgn_map()

        self.add_default_compartments = add_default_compartments
        self.schema_manager = schema_manager

        self.nodes = {}
        self.edges = {}

        self.read_nodes()
        self.read_edges()

        logger.info(f"Initialized SBGNAdapter with data source: {self.data_source}")

    def _load_sbgn_map(self) -> Any:
        """Load and parse the SBGN file using momapy or fallback XML parser."""

        logger.info(f"Loading SBGN file: {self.data_source}")
        
        result = momapy.io.read(self.data_source, return_type="model")
        if not hasattr(result, "obj") or result.obj is None:
            raise ValueError(f"Failed to parse SBGN file: {self.data_source}")

        logger.info("SBGN file loaded successfully")

        return result.obj

    def _get_glyph_class(self, glyph) -> str:
        """Extract class from a glyph, handling different attribute names."""
        if hasattr(glyph, "class_"):
            return glyph.class_
        elif hasattr(glyph, "class"):
            return getattr(glyph, "class")
        elif hasattr(glyph, "glyph_class"):
            return glyph.glyph_class
        else:
            return glyph.__class__.__name__

    def extract_glyph_schema_labels(self, label):
        node_type, sbo_term, parent_glyph = self.GLYPH_CLASS_TO_NODE_TYPE.get(
            label.lower(), self.GLYPH_CLASS_TO_NODE_TYPE["physical entity"])
        
        child_type = node_type
        while parent_glyph != None and self.schema_manager:
            self.schema_manager.add_child(parent_glyph, child_type)
            child_type, _, parent_glyph = self.GLYPH_CLASS_TO_NODE_TYPE.get(
                parent_glyph.lower(), (None, None, None))
            
        return node_type, sbo_term
            
    def extract_edge_schema_labels(self, label):
        edge_type, sbo_term, parent_glyph = self.ARC_CLASS_TO_EDGE_TYPE.get(
            label.lower(), self.ARC_CLASS_TO_EDGE_TYPE["process"])
        
        child_type = edge_type
        while parent_glyph != None and self.schema_manager:
            self.schema_manager.add_child(parent_glyph, child_type)
            child_type, _, parent_glyph = self.ARC_CLASS_TO_EDGE_TYPE.get(
                parent_glyph.lower(), (None, None, None))
            
        return edge_type, sbo_term

    def read_nodes(self):
        """
        Extract nodes from the SBGN file.

        Yields:
            Tuples of (node_id, node_label, properties_dict) for each node
        """
        logger.info("Extracting nodes from SBGN file")

        # Check if we're using the XML fallback (dict structure)
        glyphs = []
        processes = []
        if isinstance(self.sbgn_map, dict):
            glyphs = self.sbgn_map.get("glyphs", [])
        else:
            if hasattr(self.sbgn_map, "entity_pools"):
                glyphs = self.sbgn_map.entity_pools
            if hasattr(self.sbgn_map, "processes"):
                processes = self.sbgn_map.processes  

        node_count = 0
        for glyph in glyphs:            
            # momapy object structure
            # Skip nested glyphs (e.g., unit of information inside nucleic acid feature)
            # Only process top-level glyphs
            glyph_id = None
            if hasattr(glyph, "id_"):
                glyph_id = glyph.id_

            if not glyph_id:
                continue

            # Get glyph class
            glyph_class = self._get_glyph_class(glyph)
            
            # Map to BioCypher node type
            node_type, sbo_term = self.extract_glyph_schema_labels(glyph_class.lower())

            # Extract label
            label_text = getattr(glyph, "label", "")

            # Build properties
            properties: Dict[str, Any] = {
                "sbgn_class": glyph_class,
                "sbgn_id": glyph_id,
            }

            if sbo_term:
                properties["sbo_term"] = sbo_term

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
                            sub_label = getattr(sub_glyph, "label", "")
                            if sub_label:
                                unit_info.append(sub_label)
                    if unit_info:
                        properties["unit_of_information"] = unit_info

            self.nodes[glyph] = (glyph_id, node_type, properties)
            node_count += 1

        for process in processes:
            node_type, sbo_term = self.extract_glyph_schema_labels("process")
            if hasattr(process, "id_"):
                self.nodes[process] = (process.id_, node_type, {"sbo_term": sbo_term, "sbgn_class": "process", "sbgn_id": process.id_})
                node_count += 1


        logger.info(f"Extracted {node_count} nodes from SBGN file")

    def read_edges(self):
        """
        Extract edges from the SBGN file.

        Yields:
            Tuples of (edge_id, source_id, target_id, edge_type, properties_dict)
            for each edge
        """
        logger.info("Extracting edges from SBGN file")
        # Check if we're using the XML fallback (dict structure)

        edge_count = 0

        # Access arcs from the map (momapy structure)
        modulations = []
        processes = []
        if hasattr(self.sbgn_map, "modulations"):
            modulations = self.sbgn_map.modulations
        if hasattr(self.sbgn_map, "processes"):
            processes = self.sbgn_map.processes

        for modulation in modulations:

            edge_id = getattr(modulation, "id_", None)

            arc_class = modulation.__class__.__name__ if hasattr(modulation, "__class__") else "unknown"

            # Map to BioCypher edge type
            edge_type, sbo_term = self.extract_edge_schema_labels(arc_class.lower())

            # Resolve endpoints
            source_id = None
            target_id = None
            if hasattr(modulation, "source"):
                source_id = getattr(modulation.source, "id_", None)
            if hasattr(modulation, "target"):
                target_id = getattr(modulation.target, "id_", None)
            
            if not source_id or not target_id:
                logger.warning(f"Could not resolve endpoints for modulation {edge_id}")
                continue
        
            properties: Dict[str, Any] = {}
            # momapy object structure
            # Extract arc ID if available
            if hasattr(modulation, "id_"):
                properties["sbgn_arc_id"] = modulation.id_

            if sbo_term:
                properties["sbo_term"] = sbo_term

            # Extract start/end coordinates if available
            if hasattr(modulation, "start"):
                start = modulation.start
                if hasattr(start, "x") and hasattr(start, "y"):
                    properties["start_x"] = float(start.x) if start.x is not None else None
                    properties["start_y"] = float(start.y) if start.y is not None else None

            if hasattr(modulation, "end"):
                end = modulation.end
                if hasattr(end, "x") and hasattr(end, "y"):
                    properties["end_x"] = float(end.x) if end.x is not None else None
                    properties["end_y"] = float(end.y) if end.y is not None else None

            # Extract intermediate points if available
            if hasattr(modulation, "next") or hasattr(modulation, "points"):
                points = []
                if hasattr(modulation, "next"):
                    # Handle next points
                    next_point = modulation.next
                    while next_point:
                        if hasattr(next_point, "x") and hasattr(next_point, "y"):
                            points.append(
                                {
                                    "x": float(next_point.x) if next_point.x is not None else None,
                                    "y": float(next_point.y) if next_point.y is not None else None,
                                }
                            )
                        next_point = getattr(next_point, "next", None)
                elif hasattr(modulation, "points"):
                    for point in modulation.points:
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

            self.edges[modulation] = (edge_id, source_id, target_id, edge_type, properties)
            edge_count += 1

        for process in processes:
            
            glyph_id = getattr(process, "id_", None)

            for reactant in getattr(process, "reactants", []):
                source_id = getattr(reactant, "id_", None)
                target_id = glyph_id
                edge_id = f"{source_id}_reactant_{target_id}"
                if not source_id or not target_id:
                    logger.warning(
                        f"Could not resolve endpoints for reactant in process {edge_id}"
                    )
                    continue

                arc_class = "reactant"
                edge_type, sbo_term = self.extract_edge_schema_labels(arc_class.lower())

                properties: Dict[str, Any] = {
                    "sbgn_arc_class": arc_class,
                }
                if sbo_term:
                    properties["sbo_term"] = sbo_term

                self.edges[reactant] = (edge_id, source_id, target_id, edge_type, properties)
                edge_count += 1

            for product in getattr(process, "products", []):
                source_id = glyph_id
                target_id = getattr(product, "id_", None)
                edge_id = f"{source_id}_product_{target_id}"
                if not source_id or not target_id:
                    logger.warning(
                        f"Could not resolve endpoints for product in process {edge_id}"
                    )
                    continue

                arc_class = "product"
                edge_type, sbo_term = self.extract_edge_schema_labels(arc_class.lower())

                properties: Dict[str, Any] = {
                    "sbgn_arc_class": arc_class,
                }
                if sbo_term:
                    properties["sbo_term"] = sbo_term

                self.edges[product] = (edge_id, source_id, target_id, edge_type, properties)
                edge_count += 1

        logger.info(f"Extracted {edge_count} edges from SBGN file")

    def get_nodes(self) -> Iterator[Tuple[str, str, Dict[str, Any]]]:
        """Return stored nodes."""
        for node in self.nodes.values():
            yield node
    
    def get_edges(self) -> Iterator[Tuple[str, str, str, str, Dict[str, Any]]]:
        """Return stored edges."""
        for edge in self.edges.values():
            yield edge