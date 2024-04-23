# This file is for custom exceptions specific to the project
from typing import Optional


class PipeLineException(Exception):
    pass


class PreviousNodesNotRun(PipeLineException):
    def __init__(self, err: str = None):
        """
        Exception used to indicate that a particular node can't run.
        Parameters
        ----------
        err : str
            String giving additional context to the exception.
        """
        msg = "The previous nodes in the pipeline have not been run"
        if err is None:
            msg += "."
        else:
            msg += f": {err}"
        super().__init__(msg)
        return


class NodeRequirementsNotMet(PipeLineException):
    def __init__(self,
                 unmet_reqs: list = None,
                 reqs: list = None):
        """
        Exception used to indicate that a node's _requirements are not met; _previous nodes do not produce the expected
        modifications to the AnnData object.
        Parameters
        ----------
        unmet_reqs : list
            List of _requirements that have not been met.
        reqs : list
            List of _requirements for the node.
        """
        msg = "The _requirements of this node have not been met"
        if unmet_reqs is None or reqs is None:
            msg += "."
        else:
            msg += f": {unmet_reqs} not in {reqs}."
        super().__init__(msg)
        return


class NodeException(PipeLineException):
    def __init__(self,
                 exception: Exception = None,
                 node: Optional = None):
        """
        Exception used to indicate a general exception in a node.
        Parameters
        ----------
        exception : Exception
            The exception that was raised.
        node : PipelineNode
            Node instance that raised the error. Should have the .depth attribute set for additional info,
                 but isn't necessary.
        """
        node_msg = ""
        if node is not None:
            node_msg = f" ({str(node)} at depth {node.depth})"

        err_msg = f"\n-----------------------------------\nAn exception occurred in a node{node_msg}:\n"
        err_msg += f"{type(exception).__name__}: {str(exception)}"
        super().__init__(err_msg)
        return


class ParameterInitializationError(Exception):
    def __init__(self,
                 msg: str = "",
                 parameter_name: str = None,
                 casting_type: str = None,
                 exception: Exception = None,
                 node: Optional = None):
        """Error to indicate that the node's parameters could not be correctly initialized."""
        if msg is None:
            msg = ""
        if node is not None:
            node_name = node["procName"]
            node_module = node["module"]
            parameter_value = node["paramsValues"][parameter_name]
            parameter_msg = (f"There was a problem with the node \"{node_name}\" from module {node_module}. "
                             f"Unable to set parameter \"{parameter_name}\" with intended value {parameter_value} to "
                             f"type {casting_type}")
            if len(msg) > 0:
                msg += f" - {parameter_msg}"
            msg += f"\n{type(exception).__name__}: {str(exception)}"
            super().__init__(msg)
            return