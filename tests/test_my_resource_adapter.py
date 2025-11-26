"""
Tests for MyResourceAdapter.
"""

import pytest
from pathlib import Path
import tempfile
import pandas as pd

from sys_bio_kgs.adapters.my_resource_adapter import MyResourceAdapter


class TestMyResourceAdapter:
    """Test the MyResourceAdapter."""
    
    def test_adapter_initialization(self):
        """Test that the adapter initializes correctly."""
        adapter = MyResourceAdapter("test_data_source.csv")
        
        assert adapter.data_source == "test_data_source.csv"
        assert adapter.config == {}
    
    def test_adapter_initialization_with_config(self):
        """Test that the adapter initializes with additional config."""
        config = {"param1": "value1", "param2": "value2"}
        adapter = MyResourceAdapter("test_data_source.csv", **config)
        
        assert adapter.data_source == "test_data_source.csv"
        assert adapter.config == config
    
    def test_get_metadata(self):
        """Test that metadata is returned correctly."""
        adapter = MyResourceAdapter("test_data_source.csv")
        metadata = adapter.get_metadata()
        
        assert metadata["name"] == "MyResourceAdapter"
        assert metadata["data_source"] == "test_data_source.csv"
        assert metadata["data_type"] == "csv"
        assert metadata["version"] == "0.1.0"
        assert metadata["adapter_class"] == "MyResourceAdapter"
    
    def test_get_nodes_with_csv_file(self):
        """Test node extraction from CSV file."""
        # Create a temporary CSV file
        test_data = pd.DataFrame({
            'id': ['1', '2', '3'],
            'name': ['Protein A', 'Gene B', 'Compound C'],
            'type': ['protein', 'gene', 'compound']
        })
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            test_data.to_csv(f, index=False)
            temp_file = f.name
        
        try:
            adapter = MyResourceAdapter(temp_file)
            nodes = list(adapter.get_nodes())
            
            # Adapter now returns dummy data, not CSV data
            # Check that nodes are tuples with 3 elements (node_id, node_label, properties_dict)
            assert len(nodes) > 0
            assert isinstance(nodes[0], tuple)
            assert len(nodes[0]) == 3
            node_id, node_label, properties = nodes[0]
            assert isinstance(node_id, str)
            assert isinstance(node_label, str)
            assert isinstance(properties, dict)
        finally:
            Path(temp_file).unlink()
    
    def test_validate_data_source_with_existing_csv(self):
        """Test data source validation with existing CSV file."""
        # Create a temporary CSV file
        test_data = pd.DataFrame({'id': ['1'], 'name': ['test']})
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            test_data.to_csv(f, index=False)
            temp_file = f.name
        
        try:
            adapter = MyResourceAdapter(temp_file)
            assert adapter.validate_data_source() is True
        finally:
            Path(temp_file).unlink()
    
    def test_validate_data_source_with_nonexistent_file(self):
        """Test data source validation with non-existent file."""
        adapter = MyResourceAdapter("nonexistent_file.csv")
        assert adapter.validate_data_source() is False
    
    def test_get_edges_empty(self):
        """Test that edges are returned."""
        adapter = MyResourceAdapter("test_data_source.csv")
        edges = list(adapter.get_edges())
        
        # Adapter now returns dummy edges
        # Check that edges are tuples with 5 elements (source_id, target_id, edge_label, edge_type, properties_dict)
        assert isinstance(edges, list)
        assert len(edges) > 0
        assert isinstance(edges[0], tuple)
        assert len(edges[0]) == 5
        source_id, target_id, edge_label, edge_type, properties = edges[0]
        assert isinstance(source_id, str)
        assert isinstance(target_id, str)
        assert isinstance(edge_label, str)
        assert isinstance(edge_type, str)
        assert isinstance(properties, dict)