#!/usr/bin/env python3
"""
sys-bio-kgs - A repository for the implementations of the 2025 BioHackathon Germany that do not have another home already

This script creates a knowledge graph using BioCypher and the SBGNAdapter.
"""

import logging
from pathlib import Path

from biocypher import BioCypher
from sys_bio_kgs.adapters.sbgn_adapter import SBGNAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to create the knowledge graph."""
    logger.info("Starting sys-bio-kgs knowledge graph creation")
    
    # Initialize BioCypher
    bc = BioCypher(
        biocypher_config_path="config/biocypher_config.yaml",
        schema_config_path="config/schema_config.yaml"
    )
    
    # Initialize the SBGN adapter
    data_source = "data/Repressilator_PD_v7.sbgn"
    
    adapter = SBGNAdapter(
        data_source=data_source,
        # Add any additional configuration parameters here
    )
    
    # Create the knowledge graph
    logger.info("Creating knowledge graph...")
    bc.write_nodes(adapter.get_nodes())
    bc.write_edges(adapter.get_edges())
    
    logger.info("Knowledge graph creation completed successfully!")

    # Create import script and final summary
    bc.write_import_call()
    bc.summary()


if __name__ == "__main__":
    main()
