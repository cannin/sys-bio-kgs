import momapy.sbml.io.sbml
import momapy.io


class SBMLCommonSchemaAdapter(object):
    def __init__(self, file_path):
        self.file_path = file_path
        self.obj = None

    def load(self):
        self.obj = momapy.io.read(self.file_path).obj

    def get_nodes_and_relationships(self):
        if self.obj is None:
            raise ValueError("model should be loaded first")
        all_nodes = []
        all_relationships = []
        for species in self.obj.species:
            nodes, relationships = self._make_nodes_and_relationsips_from_species(
                species
            )
            all_nodes += nodes
            all_relationships += relationships
        for compartment in self.obj.compartments:
            nodes, relationships = self._make_nodes_and_relationships_from_compartment(
                compartment
            )
            all_nodes += nodes
            all_relationships += relationships
        for reaction in self.obj.reactions:
            nodes, relationships = self._make_nodes_and_relationships_from_reaction(
                reaction
            )
            all_nodes += nodes
            all_relationships += relationships
        return all_nodes, all_relationships

    @classmethod
    def _make_nodes_and_relationsips_from_species(cls, species):
        nodes = [(species.id_, "entity", {"name": species.name})]
        if species.compartment is not None:
            relationships = [
                (
                    str(hash((species, species.compartment))),
                    species.id_,
                    species.compartment.id_,
                    "contained entity",
                    {},
                )
            ]
        else:
            relationships = []
        return nodes, relationships

    @classmethod
    def _make_nodes_and_relationships_from_compartment(cls, compartment):
        nodes = [(compartment.id_, "compartment", {"name": compartment.name})]
        relationships = []
        return nodes, relationships

    @classmethod
    def _make_nodes_and_relationships_from_reaction(cls, reaction):
        nodes = [(reaction.id_, "process", {"name": reaction.name})]
        relationships = []
        for reactant in reaction.reactants:
            source_node_id = reactant.referred_species.id_
            target_node_id = reaction.id_
            if reactant.stoichiometry is not None:
                properties = {"stoichiometry": reactant.stoichiometry}
            else:
                properties = {}
            relationships.append(
                (
                    reactant.id_,
                    source_node_id,
                    target_node_id,
                    "reactant",
                    properties,
                )
            )
        for product in reaction.products:
            source_node_id = product.referred_species.id_
            target_node_id = reaction.id_
            if product.stoichiometry is not None:
                properties = {"stoichiometry": product.stoichiometry}
            else:
                properties = {}
            relationships.append(
                (
                    product.id_,
                    source_node_id,
                    target_node_id,
                    "product",
                    properties,
                )
            )
        for modifier in reaction.modifiers:
            source_node_id = modifier.referred_species.id_
            target_node_id = reaction.id_
            relationships.append(
                (
                    modifier.id_,
                    source_node_id,
                    target_node_id,
                    "modifier",
                    {},
                )
            )
        return nodes, relationships
