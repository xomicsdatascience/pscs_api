# This file parses available nodes and creates a JSON object describing coarse node properties
# for use by the pipeline designer.
from __future__ import annotations
import importlib.util
from os.path import join, basename, dirname
from pscs_api.base import InputNode, OutputNode, Pipeline, PipelineNode
from pscs_api.exceptions import ParameterInitializationError
from werkzeug.utils import secure_filename
import os
import json
from importlib import import_module
import inspect
from typomancy.handlers import type_wrangler
from argparse import ArgumentParser
from typing import Collection
import sys
from pathlib import Path
from collections import defaultdict as dd


def without_leading_underscore(d: dict) -> list:
    """
    Parses the keys of a dict and returns a list of those without leading underscores.
    Parameters
    ----------
    d : dict
        Dict whose key should be parsed

    Returns
    -------
    list
        List of keys without leading underscores.
    """
    without_underscore = []
    for k in d.keys():
        if not k.startswith('_'):
            without_underscore.append(k)
    return without_underscore


def get_node_parameters(node: callable) -> dict:
    """
    Extracts the relevant node parameters from the input node.
    Parameters
    ----------
    node : callable
        Reference to a PipelineNode (or subclass) from which to extract the parameters.
    Returns
    -------
    dict
        Dictionary containing the relevant parameters.
    """
    d = dict()
    param_dict = inspect.signature(node).parameters
    params, req_params = parse_params(param_dict)
    # Check which type of node this is
    if issubclass(node, InputNode):
        d['num_inputs'] = 0
    elif issubclass(node, OutputNode):
        d['num_outputs'] = 0
    # For whatever reason, user may want to overwrite the number of inputs.
    d['num_inputs'] = node.num_inputs
    d['num_outputs'] = node.num_outputs
    d["requirements"] = node.requirements.as_list()
    d["effects"] = node.effects.as_list()
    d['parameters'] = params
    d["important_parameters"] = node.important_parameters
    d["required_parameters"] = req_params
    return d


def parse_params(params_dict: dict) -> (dict, list):
    """
    Parses the param dict and returns a dict holding only the annotation (type) and default value.
    Parameters
    ----------
    params_dict : dict
        Dict of parameters as returned by inspect.signature(callable).parameters
    Returns
    -------
    dict
        Dict of tuples of the form (annotation, default_value)
    list
        List of parameters that need to be defined by the user.
    """
    params = []
    required_params = []
    for param_name, param_value in params_dict.items():
        annot = str(param_value.annotation)
        # In case default value is empty, set to none
        default = param_value.default
        if default == inspect._empty:
            default = None
            required_params.append(param_name)
        params.append({"name": param_name, "type": annot, "default": default})
    return params, required_params


def find_unique_name(d: dict, name: str) -> str:
    """
    Creates a string from "name" that is not present in "d" by appending "_X".
    Parameters
    ----------
    d : dict
        Dictionary into which "name" is trying to fit uniquely.
    name : str
        Base name

    Returns
    -------
    str
        New name that is not in d
    """
    dkeys = d.keys()
    id = -1
    newname = name
    while newname in dkeys:
        id += 1
        newname = f"{name}_{id}"
    return newname


def load_from_nodes(node_json: str) -> Pipeline:
    """
    Loads a pipeline and its parameters from a file. Intended to be paired with the pipeline export from the website.
    Parameters
    ----------
    node_json : str
        Path to the node JSON exported from the designer.

    Returns
    -------
    Pipeline
    """
    # Load data
    f = open(node_json, 'r')
    pipeline = json.load(f)
    node_data = pipeline['nodes']
    f.close()
    node_dict = {}
    src_dict = {}
    dst_dict = {}
    for node in node_data:
        node_module = node['module']
        if node_module.endswith(".py"):
            node_module = node_module[:-3]
        node_name = node['procName']
        # Restrict imports to PSCS pipeline:
        module = import_module(f'{node_module}', package=__package__)
        node_class = inspect.getmembers(module, lambda mem: inspect.isclass(mem) and mem.__name__ == node_name)[0][1]

        # Instantiate the class with specified parameters
        # Get class annotations and convert JSON values to the type specified
        class_params = inspect.signature(node_class.__init__).parameters
        cast_params = dict()
        for param_name, param_obj in class_params.items():
            if param_name == "self":
                continue
            try:
                par = type_wrangler(node["paramsValues"][param_name], param_obj.annotation)
            except Exception as e:
                raise ParameterInitializationError(msg = None,
                                                   parameter_name=param_name,
                                                   casting_type=param_obj.annotation,
                                                   exception=e,
                                                   node=node)
            if par is None:
                par = param_obj.default
            cast_params[param_name] = par
        node_instance = node_class(**cast_params)
        node_instance.nodeId = node['nodeId']
        node_num, node_srcs, node_dsts = identify_connections(node)
        node_dict[node_num] = node_instance
        src_dict[node_num] = node_srcs
        dst_dict[node_num] = node_dsts
    connect_nodes(node_dict, src_dict)
    return node_dict


def initialize_pipeline(node_json: str, input_files: dict, output_dir: str):
    """
    Starts a pipeline by loading it from a file and setting the input files specified for the relevant nodes.
    Parameters
    ----------
    node_json : str
        Path to the node JSON exported from the designer.
    input_files : dict
        Dict keyed by the node id with values corresponding to the id_data of the file to fetch from the database.
    output_dir : str
        Leading path where files should be placed.
    Returns
    -------

    """
    pipeline_nodes = load_from_nodes(node_json)
    pipeline = Pipeline(pipeline_nodes)
    assign_inputs(pipeline, input_files=input_files)
    assign_outputs(pipeline, output_dir)
    return pipeline


def assign_outputs(pipeline: Pipeline, output_dir: str) -> None:
    """
    Adds "output_dir" as prefix to "output_name" attributes of pipeline nodes.
    Parameters
    ----------
    pipeline : Pipeline
        Pipeline whose outputs should be assigned.
    output_dir : str
        Directory where to put the outputs.

    Returns
    -------
    None
    """
    for node_num, node in pipeline.pipeline.items():
        if isinstance(node, OutputNode):
            save_name = node.parameters["save"]
            num_leading_uscore = len(save_name) - len(save_name.lstrip("_"))  # secure_filename has a hangup on uscores
            node.parameters["save"] = join(output_dir, "_"*num_leading_uscore + secure_filename(node.parameters["save"]))
    return

def assign_inputs(pipeline: Pipeline, input_files: dict, path_keyword: str = 'path') -> None:
    """
    Assigns the input files
    Parameters
    ----------
    pipeline : Pipelime
        Pipeline whose input nodes should be assigned inputs.
    input_files : dict
        Dict keyed by the node id with values corresponding to the id_data of the file to fetch from the database.
    path_keyword : str
        Keyword for the input path.

    Returns
    -------
    None
    """
    input_keys = input_files.keys()
    for node_num, node in pipeline.pipeline.items():
        if node.nodeId in input_keys:
            node.parameters[path_keyword] = input_files[node.nodeId]
    return


def connect_nodes(node_dict: dict, src_dict: dict) -> None:
    """
    Connects the nodes in node_dict according to the sources in src_dict.
    Parameters
    ----------
    node_dict : dict
        Dictionary of node instances keyed by their ID.
    src_dict : dict
        Dictionary of lists keyed by a node ID. Each ID in the list represents a node that has the key node as a source.

    Returns
    -------
    None
    """
    for key_node, node in node_dict.items():
        for srcnode in src_dict[key_node]:
            node.connect_to_output(node_dict[srcnode])
    return


def identify_connections(node: dict) -> (str, list, list):
    """
    Identifies the node's ID and input & output connections.
    Parameters
    ----------
    node : dict
        Dictionary describing a single node and its connections, as exported from the pipeline designer.

    Returns
    -------
    str
        Node ID
    list
        List of node IDs that have this node as their source.
    list
        List of node IDs that have this node as their destination.
    """
    node_id_src = -1
    node_id_dst = -1
    srcs = []
    dsts = []
    for s in node["srcConnectors"]:
        ssplit = s.split('-')
        srcs.append(ssplit[2])
        node_id_src = ssplit[1]
    for d in node['dstConnectors']:
        dsplit = d.split('-')
        dsts.append(dsplit[1])
        node_id_dst = dsplit[2]
    if node_id_dst != -1:
        node_id = node_id_dst
    elif node_id_src != -1:
        node_id = node_id_src
    else:
        raise ValueError('Could not determine ID for node.')
    return node_id, srcs, dsts


def parse_package(out_path: Path,
                  parse_directory: str = None,
                  package_name: str = None,
                  display_name: str = None):
    all_files = []
    offset = 0
    if not parse_directory.endswith(os.path.sep):
        offset = 1  # in case the parse_directory is "path/" instead of "path"
    # Walk through specified directory, find .py files that aren't __init__.py
    for dirpath, _, files in os.walk(parse_directory):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                f_path = os.path.join(dirpath, file)
                all_files.append(f_path)

    nodes = []
    module_set = set()  # We can ignore duplicates; that just means that there are multiple nodes in a file.
    for i in range(len(all_files)):
        start_modules = sys.modules  # To later undo included modules
        spec = importlib.util.spec_from_file_location(package_name, all_files[i])  # get spec for import
        module = importlib.util.module_from_spec(spec)  # define module
        sys.modules[all_files[i]] = module  # add module
        spec.loader.exec_module(module)  # load module
        # Find the class definitions in the file
        node_classes = inspect.getmembers(module, lambda mem: inspect.isclass(mem) and mem.__module__ == package_name)
        for n in node_classes:
            # importing modules uses a string of form top.second.third.[...]; also doesn't end in .py
            m = convert_path_to_modules(all_files[i][len(parse_directory) + offset:])
            module_path = ".".join([package_name, m])  # include top-level path
            module_set.add(module_path)  # track module
            node_params = get_node_parameters(n[1])  # from the class definition
            node_params["type"] = get_node_type(n[1])
            node_params["module"] = module_path  # add module info
            node_params["name"] = n[0]
            nodes.append(node_params)
        sys.modules = start_modules  # Undoing included modules

    module_list = list(module_set)
    module_list.sort()  # for reproducibility
    base_module = ModuleNest(name=module_list[0].split(".")[0])  # Start with top-level module
    for m in module_list:
        # Create the nesting structure for each module
        module_split = m.split(".")[1:]  # drop the top-level package
        parent_module = base_module  # start at the base
        for s in module_split:
            child_module = ModuleNest(name=s, parent=parent_module)  # define child module
            was_added = parent_module.add_child(child_module)  # try to add the child module
            if was_added:
                parent_module = child_module  # was added; continue to next module level
            else:
                parent_module = parent_module[s]  # was not added; take the one that's currently there
    # Add nodes
    for n in nodes:
        base_module.add_node(n["module"], n)
    package_dict = {}
    package_dict["display_name"] = display_name
    package_dict["modules"] = base_module.to_dict()
    f = open(out_path, "w")
    json.dump(package_dict, f, indent=1)
    f.close()
    return base_module


def get_node_type(node_class):
    if issubclass(node_class, InputNode):
        return "input"
    elif issubclass(node_class, OutputNode):
        return "output"
    elif issubclass(node_class, PipelineNode):
        return "simo"



class ModuleNest:
    def __init__(self,
                 name: str,
                 parent: ModuleNest = None,
                 children: list[ModuleNest] = None,
                 nodes: list = None):
        """
        A class representing the nested module/node structure of a package.
        Parameters
        ----------
        name : str
            Name of the module.
        parent : ModuleNest
            Pointer to the module that contains this module.
        children : list[ModuleNest]

        nodes
        """
        self.name = name
        self.parent = parent
        if children is not None:
            self.children = children
        else:
            self.children = []

        if nodes is not None:
            self.nodes = nodes
        else:
            self.nodes = []
        return

    def add_child(self, child: ModuleNest) -> bool:
        """
        Adds a child module to this one. Returns True if the child is new and was added, False if it is already present.
        Parameters
        ----------
        child : ModuleNest
            Child module to add.
        Returns
        -------
        bool
            Whether the child was added. If False, the child module was not added since an identically-named child
            is already there.
        """
        if self[child.name] is None:  # child doesn't appear in the list; should be added
            self.children.append(child)
            return True
        return False

    def add_node(self,
                 module_str: str,
                 node: dict,
                 first_call: bool = True):
        """
        Adds a node at the appropriate level specified by the module_str.
        Parameters
        ----------
        module_str: str
            A string representing the structure of parent modules, of the form "parent0.parent1.parent2.[...]". The
            node will be added to the last module in the string.
        node : str
            Node to add to the last module.
        first_call: bool
            Whether this is the first time the function is called; determines whether to remove the top-level module
            from the module_str.
        Returns
        -------
        None
        """
        if "." not in module_str:  # at the bottom of the module_str
            if node not in self.nodes:
                self[module_str].nodes.append(node)
        else:
            split = module_str.split(".")
            if first_call:
                split = split[1:]  # remove top-level package
            new_module_str = ".".join(split[1:])
            if len(split) == 1:
                self[split[0]].nodes.append(node)
                return
            self[split[0]].add_node(new_module_str, node, first_call=False)  # select child, go down one level
        return

    def get_node(self, module_str: str, first_call: bool = True) -> dict:
        """Gets the node at the appropriate level specified by the module_str; the last module should specify the
        name of the node. E.g., "parent0.parent1.TheNodeToGet" """
        s = module_str.split(".")
        if first_call:
            s = s[1:]  # remove top-level package if this is the shallowest call
        if len(s) == 2:  # node is stored at this level
            for n in self[s[0]].nodes:
                if n["name"] == s[1]:
                    return n
            raise KeyError(f"No such node: {s[1]}")
        else:
            return self[s[0]].get_node(".".join(s[1:]), first_call=False)  # go down one more level


    def summarize(self, depth=0, show_nodes: bool = True):
        """Creates a string summarizing the nested structure of the modules. Modules containing other modules are
         indicated with an arrow (→), nodes are indicated with a bullet point (•)."""
        spacing = "  "
        tabs = spacing*depth
        node_str = ""
        if show_nodes:
            for n in self.nodes:
                node_str += f"\n{tabs}{spacing}•{n['name']}"
        if self.children is not None:
            if len(self.children) >= 1:
                return f"{tabs}{self.name} → {node_str}{self.summarize_list(self.children, depth=depth+1, show_nodes=show_nodes)}"
            else:
                return f"{tabs}{self.name}{node_str}"
        else:
            return f"{tabs}{self.name}{node_str}"

    @staticmethod
    def summarize_list(lst: list[ModuleNest], depth=0, show_nodes=True):
        """Summarizes the list; mostly used for children of modules."""
        s = ""
        for m in lst:
            s += "\n"
            s += m.summarize(depth, show_nodes=show_nodes)
        return s

    def __str__(self):
        return self.name

    def __getitem__(self, key):  # allows to get child modules via n[child]
        for c in self.children:
            if c.name == key:
                return c
        return None

    def to_dict(self):
        """Converts the nested structure to a single dictionary."""
        return {"name": self.name, "modules": [c.to_dict() for c in self.children], "nodes": self.nodes}


def convert_pathlist_to_modules(pathlist: list) -> list:
    module_list = []
    for path in pathlist:
        module_list.append(convert_path_to_modules(path))
    return module_list


def convert_path_to_modules(path: str) -> str:
    """Converts a file path to modules."""
    module_chain = ".".join(path.split(os.path.sep))
    if module_chain.endswith(".py"):
        module_chain = module_chain[:-len(".py")]
    return module_chain



def gather_files(parse_directory: str = None,
                 exclude_files: list = None):
    """Gathers all files in a directory that aren't explicitly marked for exclusion"""
    if exclude_files is None:
        exclude_files = []
    exclude_files = set(exclude_files)
    all_files = set()
    for dirname, _, filenames in os.walk(parse_directory):
        for f in filenames:
            if f.endswith(".py") and f not in exclude_files:
                all_files.add(os.path.join(dirname, f))
    return all_files


def remove_excluded_files(files: Collection[str],
                          exclude_files: Collection[str] = None) -> list:
    """Removes entries of exclude_files from file_list"""
    if exclude_files is None:
        return files
    file_set = set(files)
    exclude_set = set(exclude_files)
    return list(file_set.difference(exclude_set))


def remove_notpy(files: Collection[str]) -> list:
    """Removes entries in file_list that don't end in .py"""
    exclude_files = set()
    for f in files:
        if not f.endswith(".py"):
            exclude_files.add(f)
    return remove_excluded_files(files, exclude_files)


def determine_name(package_name: str = None,
                   parse_directory: str = None,
                   parse_files: list = None) -> str:
    """Returns a name for the package to be parsed."""
    if package_name is not None:
        return package_name
    elif parse_directory is not None and len(parse_directory) > 0:
        return basename(parse_directory)
    elif parse_files is not None and isinstance(parse_files, list) and len(parse_files) > 0:
        return basename(parse_files[0])
    else:
        raise ValueError("No valid package name could be determined.")


if __name__ == "__main__":
    parser = ArgumentParser(prog="PSCS node parser",
                            description="This command examines the files in the specified directory and converts the "
                                        "Python node definitions to JSON in order to be displayed.")
    parser.add_argument("directory",
                        help="The directory containing the .py files that describe the nodes.")
    parser.add_argument("-n", "--name",
                        default=None,
                        help="Name of the package; defaults to the name of the directory to be parsed, or the "
                             "containing directory of the first file if no directory is provided.")
    parser.add_argument("-d", "--display",
                        default="Custom module", type=str,
                        help="Name to display for the package name."
                        )
    parser.add_argument("-o", "--output", help="Path for node data json.", type=str,
                        default="node_data.json")
    args = parser.parse_args()
    parse_package(out_path=Path(args.output),
                  parse_directory=args.directory,
                  package_name=args.name,
                  display_name=args.display)
