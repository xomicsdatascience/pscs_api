# This file describes the abstract classes that custom nodes should inherit from.
from __future__ import annotations
from abc import ABC, abstractmethod
from pscs_api.exceptions import PreviousNodesNotRun, NodeRequirementsNotMet, NodeException
from warnings import warn
import re
from copy import deepcopy
from typing import Collection
from collections import defaultdict as dd
import anndata as ad
from pscs_api.interactions import istr, interaction_fstring, interaction_pattern, interaction_parameter_string
from pscs_api.interactions import Interaction, InteractionList


class _ResultList:
    def __init__(self, elements):
        self.elements = elements

    def __getitem__(self, index):
        return self.elements[index].result


class PipelineNode(ABC):
    """
    Class for describing an individual pipeline segment, with all necessary classes indicated.
    """
    important_parameters = None  # parameters to prioritize for display
    num_inputs = 1
    num_outputs = 1
    effects = InteractionList()
    requirements = InteractionList()

    def __init__(self):
        self.has_run = False  # whether the node has been run
        self.parameters = {}  # settings used to run the node's code
        self.effects = deepcopy(self.effects)  # convert to instance variable
        self.requirements = deepcopy(self.requirements)  # convert to instance variable
        self._next = []  # list of nodes that follow this one
        self._previous = []  # list of nodes that lead to this node
        self._result = None  # stored output
        self._depth = None  # how far from the input this node is
        self._raw_effects = None
        self._raw_requirements = None
        return

    @abstractmethod
    def run(self):
        """
        Method for executing this node's effects.
        """
        return

    @staticmethod
    def store_vars_as_parameters(**kwargs):
        self = kwargs["self"]
        for param, value in kwargs.items():
            if param == "self" or param == "return" or param.startswith("_"):
                continue
            if value is None or value == "null":
                self.parameters[param] = None
            else:
                self.parameters[param] = value

    @property
    def cumulative_effect(self) -> Interaction:
        """
        Gets the _effect of all preceding nodes, appends its own _effect, and returns the list
        Returns
        -------
        Interaction
            The cumulative effects of all nodes up to this point, including the current node.
        """
        cumul = Interaction()
        for prev in self._previous:
            cumul += prev.cumulative_effect
        return cumul + self.effects

    @property
    def cumulative_requirements(self) -> Interaction:
        """
        Gets the _requirements of all preceding nodes, appends its own _requirements, and returns the list. This is most
        useful when compared with a node's cumulative _effect.
        Returns
        -------
        Interaction
            The cumulative requirements of all nodes up to this point, including the current node.
        """
        requirements = Interaction()
        for prev in self._previous:
            requirements += prev.cumulative_requirements
        return requirements + self.requirements

    @property
    def result(self):
        # Check if we have multiple outputs
        if len(self._next) > 1:
            # Return a copy of the data to prevent cross-contamination
            return deepcopy(self._result)
        else:
            return self._result

    @result.setter
    def result(self, value):
        self._result = value
        return

    @property
    def is_complete(self) -> bool:
        return self._result is not None

    @property
    def is_ready(self) -> bool:
        """Checks whether all inputs to this node have a result."""
        for p in self._previous:
            if not p.is_complete:
                return False
        return True

    @property
    def depth(self) -> int:
        """How far away the node is from the input."""
        # This function is recursive; this prevents an infinite loop if the user has a cycle in their pipeline.
        if self._depth is not None:
            return self._depth
        if isinstance(self, InputNode):
            self._depth = 0
            return self._depth
        self._depth = max([n.depth for n in self._previous]) + 1
        return self._depth

    @property
    def input_data(self):
        return _ResultList(self._previous)


    def __str__(self):
        return f"{type(self).__name__}"

    def connect_to_output(self, node):
        """
        Connects the output of this node to the input of the specified node.
        Parameters
        ----------
        node : PipelineNode
            Node whose input should be connected.
        Returns
        -------
        None
        """
        self._next.append(node)
        node._previous.append(self)
        return

    def connect_to_input(self, node):
        """
        Connects the input of this node to the output of the specified node.
        Parameters
        ----------
        node : PipelineNode
            Node whose output should be connected

        Returns
        -------
        None
        """
        self._previous.append(node)
        node._next.append(node)
        return

    def reset(self):
        """Resets the output value of the node."""
        self.result = None
        return

    def check_requirements_met(self,
                               effects: InteractionList = None,
                               reqs: InteractionList = None) -> bool:
        if isinstance(effects, Interaction):
            effects = InteractionList(effects)
        if isinstance(reqs, Interaction):
            reqs = InteractionList(reqs)

        if effects is None:
            effects = InteractionList()
        if reqs is None:
            reqs = self.requirements
        effects.product(self.effects)
        if effects >= reqs:
            return True
        else:
            reqs_met = False
            for prev in self._previous:
                reqs_met = prev.check_requirements_met(effects=effects, reqs=reqs)
                if reqs_met:
                    break
            return reqs_met

    def resolve_interactions(self):
        """Resolves effects/requirements that are parameter-dependent into their finalized values."""
        # Store raw value in case parameters change and the interactions need to be resolved again
        if self._raw_effects is None:
            self._raw_effects = deepcopy(self.effects)
        if self._raw_requirements is None:
            self._raw_requirements = deepcopy(self.requirements)
        # Restore raw values
        self.effects = deepcopy(self._raw_effects)
        self.requirements = deepcopy(self._raw_requirements)
        # Resolve effects
        for meta_interaction in [self.effects, self.requirements]:
            for interaction in meta_interaction:
                for v in vars(interaction):
                    to_swap = dd(list)
                    for val in getattr(interaction, v):
                        to_swap[val] += self._resolve_parameter_string(val)
                    for val_match, param_value in to_swap.items():
                        # param_value might be Collection, and each should be considered a separate requirement
                        interaction_set = getattr(interaction, v)
                        if isinstance(param_value, Collection) and not isinstance(param_value, str):
                            interaction_set.discard(val_match)
                            for param_subvalue in param_value:
                                if param_subvalue is not None:
                                    interaction_set.add(param_subvalue)
                        else:
                            interaction_set.discard(val_match)
                            if param_value is not None:
                                interaction_set.add(param_value)
        return

    def _resolve_parameter_string(self, pstr: str):
        resolved_strings = []
        # Fully resolve the string
        parameter_names = re.findall(interaction_pattern, pstr)
        resolving_str = pstr
        for pname in parameter_names:
            parameter_values = self.parameters[pname]
            to_replace = istr(pname)
            if isinstance(parameter_values, Collection) and not isinstance(parameter_values, str):
                for pvalue in parameter_values:
                    if pvalue is not None:
                        replace_with = str(pvalue)
                        subresolving_str = resolving_str.replace(to_replace, replace_with)
                        # Resolve remainder
                        resolved_strings += self._resolve_parameter_string(subresolving_str)
                    else:
                        continue
                return resolved_strings
            else:
                if parameter_values is not None:
                    resolving_str = resolving_str.replace(to_replace, str(parameter_values))
                else:
                    return [None]
        return resolved_strings + [resolving_str]

    def _terminate(self,
                   result=None):
        """
        Runs commands to finish the run.
        Parameters
        ----------
        result
            Result of the node to store.

        Returns
        -------
        None
        """
        self.result = result
        if not isinstance(result, ad.AnnData):
            warn(f"Node {self} at depth {self.depth} is passing data downstream that is not an AnnData object. "
                 f"Compatability with other nodes is not guaranteed and may result in unanticipated downstream effects.")
        self.has_run = True
        return


class InputNode(PipelineNode):
    """
    Input node prototype; serves to indicate that the node loads data from disk.
    """
    num_inputs = 0
    def __init__(self):
        super().__init__()
        self.num_inputs = 0

    def connect_to_input(self, node):
        raise ValueError(f"This node doesn't receive input.")


class OutputNode(PipelineNode):
    """
    Output node prototype; serves to indicate that the node produces a file to disk.
    """
    num_outputs = 0
    interactive_tag = ""  # if the output is intended to be used for an interactive app, supply the tag(s) here

    def __init__(self):
        super().__init__()
        self.num_outputs = 0

    def connect_to_output(self, node):
        raise ValueError(f"This node doesn't have an output to be received.")

    def _terminate(self,
                   result=None):
        """Output nodes don't need to store results."""
        pass


class Pipeline:
    def __init__(self, nodes: dict = None):
        """
        Class for storing, designing, and running related processes. Useful for keeping track of results and pipelines run.
        Parameters
        ----------
        nodes : dict
            Nodes indexed by their ID. Default: None    .
        """
        self.pipeline = nodes
        return

    def run(self):
        # Get how many are ready, how many are done
        ready_list = []
        for _, node in self.pipeline.items():
            if node.is_ready:
                ready_list.append(node)
        while len(ready_list) > 0:
            run_list = ready_list
            ready_list = []
            for node in run_list:
                if not node.has_run:  # prevent circular execution
                    try:
                        node.run()
                        if not node.has_run and node.result is not None:
                            warn(f"Node {node} at depth {node.depth} did not terminate correctly. The `_terminate()` method should be "
                                 f"called after node execution is complete. The node produced results, so the pipeline will continue "
                                 f"executing. Please contact the developers to fix the issue.")
                        elif node.result is None and not isinstance(node, OutputNode):
                            raise NodeException(ValueError(f"A node did not produce results. Pipeline halted."), node=node)
                    except Exception as e:
                        raise NodeException(e, node=node)
                for next_node in node._next:
                    if next_node.is_ready and not next_node.has_run:
                        ready_list.append(next_node)
        return

    def reset(self):
        for p in self.pipeline:
            p.reset()
        return
