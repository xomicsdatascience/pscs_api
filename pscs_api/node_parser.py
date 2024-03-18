# This file parses available nodes and creates a JSON object describing coarse node properties
# for use by the pipeline designer.
import importlib.util
from os.path import join, basename, dirname
from pscs_api.base import InputNode, OutputNode, Pipeline
from werkzeug.utils import secure_filename
import os
import json
from importlib import import_module
import inspect
from typomancy.handlers import type_wrangler
from argparse import ArgumentParser
from typing import Collection
import sys


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
    params = parse_params(param_dict)
    # To support MIMO nodes in the designer, this part needs to be updated.
    # Check which type of node this is
    d['num_inputs'] = 1
    d['num_outputs'] = 1
    if issubclass(node, InputNode):
        d['num_inputs'] = 0
    elif issubclass(node, OutputNode):
        d['num_outputs'] = 0
    d['parameters'] = params
    d["important_parameters"] = node.important_parameters
    return d


def parse_params(params_dict: dict) -> dict:
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
    """
    params = {}
    for param_name, param_value in params_dict.items():
        annot = str(param_value.annotation)
        # In case default value is empty, set to none
        default = param_value.default
        if default == inspect._empty:
            default = None
        params[param_name] = (annot, default)
    return params


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

        module = import_module(f'pscs_scanpy.{node_module}', package=__package__)
        last_uscore = node_name.rfind('_')  # this is in case name mangling is necessary
        if last_uscore != -1:
            node_name = node_name[:last_uscore]
        node_class = inspect.getmembers(module, lambda mem: inspect.isclass(mem) and mem.__name__ == node_name)[0][1]

        # Instantiate the class with specified parameters
        # Get class annotations and convert JSON values to the type specified
        class_params = inspect.signature(node_class.__init__).parameters
        cast_params = dict()
        for param_name, param_obj in class_params.items():
            if param_name == "self":
                continue
            par = type_wrangler(node["paramsValues"][param_name], param_obj.annotation)
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


def main(out_path: str,
         parse_directory: str = None,
         exclude_files: list = None,
         parse_files: list = None,
         package_name: str = None,
         overwrite: bool = False
         ):
    """
    Identifies files that should be parsed to obtain node specs.
    Parameters
    ----------
    out_path : str
        Where to save the node specification file.
    parse_directory : str
        Optional. Top-level directory for project containing node specs. Will recursively search through subdirectories.
    exclude_files : list
        Optional. List of files that should not be parsed.
    parse_files : list
        Optional. List of files to parse.
    package_name : str
        Name of the package.
    overwrite : bool
        Whether to overwrite the file specified by out_path, if it exists

    Returns
    -------
    None
    """
    # First check if output file can be created.
    if not overwrite and os.path.exists(out_path):
        raise ValueError(f"Output file {out_path} exists and overwrite has not been set.")
    package_name = determine_name(package_name, parse_directory, parse_files)
    all_files = []
    if parse_directory is not None:
        all_files = gather_files(parse_directory)
    all_files = set(all_files)
    if parse_files is not None:
        all_files = all_files.union(parse_files)

    # Go through files and remove the ones that shouldn't be kept
    node_files = [os.path.basename(n) for n in all_files]
    node_files = remove_excluded_files(node_files, exclude_files)
    node_files = remove_notpy(node_files)
    js_dict = {}
    for module_name in node_files:  # iterate through the pipeline files
        module_name = module_name[:-3]  # remove .py
        start_modules = sys.modules
        spec = importlib.util.spec_from_file_location(module_name, join(parse_directory, module_name))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        node_classes = inspect.getmembers(module, lambda mem: inspect.isclass(mem) and mem.__module__ == module_name)
        for node_tuple in node_classes:  # iterate through the classes in the pipeline file
            node_name = node_tuple[0]
            node_name = find_unique_name(js_dict, node_name)  # in case nodes are named the same
            node_params = get_node_parameters(node_tuple[1])
            node_params['module'] = module_name
            js_dict[node_name] = node_params
        sys.modules = start_modules
    # Patch; this is to have the loaders for the HTML/JavaScript page use the first key as the pkg name
    js_dict = {package_name: js_dict}

    f = open(out_path, 'w')
    json.dump(js_dict, f, indent=1)
    f.close()
    return


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
    parser.add_argument("-e", "--exclude",
                        default=None,
                        nargs="*",
                        help="Space-separated list of files to ignore (e.g., __init__.py")
    parser.add_argument("-f", "--files",
                        default=None,
                        nargs="*",
                        help="Space-separated list of files to parse.")
    parser.add_argument("-n", "--name",
                        default=None,
                        help="Name of the package; defaults to the name of the directory to be parsed, or the "
                             "containing directory of the first file if no directory is provided.")
    args = parser.parse_args()
    main(out_path="node_data.json",
         parse_directory=args.directory,
         exclude_files=args.exclude,
         parse_files=args.files,
         package_name=args.name,
         overwrite=True)
