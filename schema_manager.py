#!/usr/bin/env python3
"""
Simplified class-based schema manager for adding child nodes to simple_schema_config.yaml

Usage:
    from schema_manager import SchemaManager
    
    # Load existing schema
    manager = SchemaManager('config/simple_schema_config.yaml')
    
    # Add child nodes
    manager.add_child('physical entity', 'protein isoform')
    manager.add_child('process', 'catalysis', properties={'rate': 'float', 'km': 'float'})
    
    # Save to new file
    manager.save('config/updated_schema.yaml')
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union


class SchemaManager:
    """
    Manages schema configuration with methods to add child nodes.
    
    Attributes:
        schema: The loaded schema dictionary
        path: Path to the original schema file
    """
    
    def __init__(self, schema_path: Union[str, Path]):
        """
        Initialize the SchemaManager by loading a schema file.
        
        Args:
            schema_path: Path to the schema YAML file (relative paths use cwd)
        """
        self.path = Path(schema_path)
        if not self.path.is_absolute():
            # Use current working directory for relative paths
            self.path = Path.cwd() / self.path
        
        if not self.path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.path}")
        
        with open(self.path, 'r') as f:
            self.schema = yaml.safe_load(f) or {}
        
        print(f"Loaded schema from: {self.path}")
    
    def add_child(
        self,
        parent: str,
        child: str,
        inherit_properties: bool = True,
        properties: Optional[Dict[str, str]] = None,
        input_label: Optional[str] = None
    ) -> 'SchemaManager':
        """
        Add a child node to the schema.
        
        Args:
            parent: Name of the parent node
            child: Name of the child node to add
            inherit_properties: Whether to inherit properties from parent (default: True)
            properties: Additional properties as dict of name:type (optional)
            input_label: Custom input label (defaults to child name)
        
        Returns:
            Self for method chaining
        
        Raises:
            ValueError: If parent node doesn't exist
        """
        # Validate parent exists
        if parent not in self.schema:
            available = ', '.join(self.schema.keys())
            raise ValueError(
                f"Parent node '{parent}' not found in schema. "
                f"Available nodes: {available}"
            )
        
        # Get parent configuration
        parent_node = self.schema[parent]
        represented_as = parent_node.get('represented_as', 'node')
        
        # Build child node
        child_node = {
            'is_a': parent,
            'inherit_properties': inherit_properties,
            'represented_as': represented_as,
            'input_label': input_label or child
        }
        
        # Add properties if provided
        if properties:
            child_node['properties'] = properties
        
        # Add to schema
        if child in self.schema:
            print(f"  Warning: Overwriting existing node '{child}'")
        
        self.schema[child] = child_node
        print(f"  Added: {child} (child of {parent})")
        
        return self  # Enable method chaining
    
    def add_children(
        self,
        parent: str,
        children: list[Union[str, tuple[str, Dict[str, Any]]]]
    ) -> 'SchemaManager':
        """
        Add multiple child nodes to the same parent.
        
        Args:
            parent: Name of the parent node
            children: List of child names or tuples of (name, kwargs_dict)
        
        Returns:
            Self for method chaining
        
        Examples:
            manager.add_children('physical entity', [
                'protein',
                'gene',
                ('macromolecule', {'properties': {'weight': 'float'}})
            ])
        """
        for child_spec in children:
            if isinstance(child_spec, str):
                self.add_child(parent, child_spec)
            elif isinstance(child_spec, tuple) and len(child_spec) == 2:
                child_name, kwargs = child_spec
                self.add_child(parent, child_name, **kwargs)
            else:
                print(f"  Warning: Skipping invalid child specification: {child_spec}")
        
        return self
    
    def remove_child(self, child: str) -> 'SchemaManager':
        """
        Remove a child node from the schema.
        
        Args:
            child: Name of the child node to remove
        
        Returns:
            Self for method chaining
        """
        if child in self.schema:
            del self.schema[child]
            print(f"  Removed: {child}")
        else:
            print(f"  Warning: Node '{child}' not found")
        
        return self
    
    def get_node(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a node configuration by name.
        
        Args:
            name: Name of the node
        
        Returns:
            Node configuration dict or None if not found
        """
        return self.schema.get(name)
    
    def get_children(self, parent: str) -> list[str]:
        """
        Get all child nodes of a parent.
        
        Args:
            parent: Name of the parent node
        
        Returns:
            List of child node names
        """
        children = []
        for name, config in self.schema.items():
            if isinstance(config, dict) and config.get('is_a') == parent:
                children.append(name)
        return children
    
    def list_nodes(self, node_type: Optional[str] = None) -> list[str]:
        """
        List all nodes in the schema, optionally filtered by type.
        
        Args:
            node_type: Filter by 'node' or 'edge' (optional)
        
        Returns:
            List of node names
        """
        if node_type:
            return [
                name for name, config in self.schema.items()
                if isinstance(config, dict) and 
                config.get('represented_as') == node_type
            ]
        return list(self.schema.keys())
    
    def save(
        self,
        output_path: Optional[Union[str, Path]] = None,
        backup: bool = False
    ) -> Path:
        """
        Save the schema to a file.
        
        Args:
            output_path: Path to save to (defaults to original path)
            backup: Create backup of existing file (default: False)
        
        Returns:
            Path where schema was saved
        """
        if output_path is None:
            output_path = self.path
        else:
            output_path = Path(output_path)
            if not output_path.is_absolute():
                # Use current working directory for relative paths
                output_path = Path.cwd() / output_path
        
        # Create backup if requested and file exists
        if backup and output_path.exists():
            backup_path = output_path.with_suffix('.yaml.bak')
            output_path.rename(backup_path)
            print(f"Backup created: {backup_path}")
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save schema
        with open(output_path, 'w') as f:
            yaml.dump(
                self.schema,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
        
        print(f"Schema saved to: {output_path}")
        return output_path
    
    def print_tree(self, parent: Optional[str] = None, indent: int = 0) -> None:
        """
        Print the schema as a tree structure.
        
        Args:
            parent: Start from this parent (None = show root nodes)
            indent: Current indentation level (for recursion)
        """
        if parent is None:
            # Show root nodes (those without 'is_a')
            print("\nSchema Tree:")
            print("=" * 50)
            for name, config in self.schema.items():
                if isinstance(config, dict) and 'is_a' not in config:
                    node_type = config.get('represented_as', 'unknown')
                    print(f"{name} [{node_type}]")
                    self.print_tree(name, indent=2)
        else:
            # Show children of parent
            children = self.get_children(parent)
            for child in children:
                config = self.schema[child]
                node_type = config.get('represented_as', 'unknown')
                props = config.get('properties', {})
                props_str = f" ({', '.join(props.keys())})" if props else ""
                print(f"{' ' * indent}├─ {child} [{node_type}]{props_str}")
                self.print_tree(child, indent=indent+2)
    
    def __repr__(self) -> str:
        """String representation of the schema manager."""
        node_count = len(self.schema)
        return f"SchemaManager(path='{self.path}', nodes={node_count})"


def main():
    """Example usage of SchemaManager."""
    
    # Load existing schema
    manager = SchemaManager('config/simple_schema_config.yaml')
    
    print("\n" + "=" * 70)
    print("EXAMPLE: Adding child nodes to schema")
    print("=" * 70 + "\n")
    
    # Add single child nodes
    print("Adding individual child nodes:")
    manager.add_child('physical entity', 'protein isoform')
    manager.add_child(
        'physical entity',
        'macromolecule',
        properties={'molecular_weight': 'float', 'sequence': 'string'}
    )
    
    # Add multiple children at once
    print("\nAdding multiple children to 'physical entity':")
    manager.add_children('physical entity', [
        'protein',
        'gene',
        'RNA',
        ('simple chemical', {'properties': {'formula': 'string', 'charge': 'int'}})
    ])
    
    # Add process children
    print("\nAdding children to 'process':")
    manager.add_children('process', [
        ('catalysis', {'properties': {'rate': 'float', 'km': 'float'}}),
        'degradation',
        'transport'
    ])
    
    # Add modifier children
    print("\nAdding children to 'modifier':")
    manager.add_children('modifier', [
        ('inhibition', {'properties': {'ki': 'float'}}),
        ('stimulation', {'properties': {'ka': 'float'}})
    ])
    
    # Print the schema tree
    manager.print_tree()
    
    # Save to new file
    print("\n" + "=" * 70)
    output_path = manager.save('config/extended_schema.yaml')
    print("=" * 70)
    
    print(f"\n✓ Done! Extended schema saved to: {output_path}")
    print(f"  Total nodes: {len(manager.schema)}")
    print(f"  Root nodes: {len([n for n, c in manager.schema.items() if isinstance(c, dict) and 'is_a' not in c])}")


if __name__ == '__main__':
    main()
