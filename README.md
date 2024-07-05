# PSCS API

The PSCS API provides the base classes for developing new custom nodes for the **P**latform for **S**ingle-**C**ell
**S**cience (PSCS). These provide the methods needed to run a pipeline.
  
## Intro  

The API covers three types of nodes: input, pipeline, and output.  
  
- Input nodes load data from disk and convert them into a known format.  
- Pipeline nodes perform the bulk of the analytical work; they specify how the data should be manipulated before being
passed to the next node.
- Output nodes perform simple operations (e.g. plotting) before saving data to the disk.
  
##  Usage  
  
The bases classes should first be imported (`from pscs_api import PipelineNode, InputNode, OutputNode`). Your custom 
nodes should then inherit from the appropriate class:  
````Python3
class MyNode(PipelineNode):
    # Parameters listed here are visible by default in the pipeline designer. This is the only effect.
    important_parameters = ["list", "of", "param", "names"]
    
    # Node parameters are set via the pipeline designer on the site; these should be the options that your analysis
    # allows the user to control.
    # Arguments should include a type hint, either a Python native type (int, float, etc.) or one of those supported
    # by the typing module (e.g. Collection, Optional, etc.). Conversion is handled by the typomancy package.
    # Typehints are used to convert the user input via the pipeline designer from a text string to the appropriate 
    # type (e.g., "1.23" could be a str or a float; specifying float would convert the input to float before being 
    # stored in the node.
    # Node parameters are available via self.parameters["param_name"]
    def __init__(self, 
                 param1: str,
                 param2: bool):
        super().__init__()  # run the initialization on PipelineNode
        self.store_vars_as_parameters(**vars())  # store + convert input parameters
        return

    # The "run" method gets called when the pipeline is executed. It should receive no arguments; settings are should 
    # be determined by the _init__ method, and data is taken from the previous node.
    def run(self):
        # ._previous contains the list of nodes leading to the current node. They are ordered by the connecting port; 
        # [0] is the top-most node, [1] the one below that, etc.
        # Once a node has been run, it stores its output in .result, waiting for other nodes to fetch when ready.
        data = self.input_data[0]
        processed_data = data + 1  # example process
        self._terminate(processed_data)  # the ._terminate method stores the result for following nodes to use
        return
````

## Reporting Issues  
Issues can be reported via the Issues tab on GitHub.
