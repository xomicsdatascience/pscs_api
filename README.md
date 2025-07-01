# PSCS API

The PSCS API provides the base classes for developing new custom nodes for the **P**latform for **S**ingle-**C**ell
**S**cience (PSCS). These provide the methods needed to run a pipeline.
  
## Intro  

The API covers three types of nodes: input, pipeline, and output.
  
- Input nodes load data from disk and convert them into a known format.
- Pipeline nodes perform the bulk of the analytical work; they specify how the data should be manipulated before being
passed to the next node.
- Output nodes save data to disk or perform simple operations (e.g. file type conversion) before saving data to disk.
    - Plotting nodes have a special type (`PlottingNode`) that can be used to make produce pickled version of plots so that they can be edited later.

Examples of entire packages implemented using the PSCS API can be seen in the [pscs_scanpy package](https://github.com/xomicsdatascience/pscs_scanpy) or the PSCS package for [scTransient](https://github.com/xomicsdatascience/scTE).

##  Usage  

### Basic example
The bases classes should first be imported (`from pscs_api import PipelineNode, InputNode, OutputNode, PlottingNode`). Your custom nodes should then inherit from the appropriate class:  
````Python3
class MyNode(PipelineNode):
    # Parameters listed here are visible by default in the pipeline designer. This is the only effect.
    important_parameters = ["param1"]
    
    # Parameter values are set via the pipeline designer on the site; these should be the options that your analysis
    # allows the user to control.
    # Node parameters are made available via self.parameters["param_name"]
    def __init__(self, 
                 param1: str,     # Arguments should include a type hint; either a Python native type (e.g. int) or 
                 param2: bool):   # one supported by the typing module (e.g. Collection, Optional, etc.)
        super().__init__()  # run the initialization on PipelineNode
        self.store_vars_as_parameters(**vars())  # store + convert input parameters
        return

    # The "run" method gets called when the pipeline is executed. It should receive no arguments; settings are should 
    # be determined by the _init__ method, and data is taken from the previous node.
    def run(self):
        # self.input_data contains the data being passed to this node. They are ordered by the connecting port.
        # Once a node has been run, it stores its output in .result, waiting for other nodes to fetch when ready.
        data = self.input_data[0]
        processed_data = data + 1  # example process
        self._terminate(processed_data)  # the ._terminate method stores the result for following nodes to use
        return
````

### Using Scanpy's argument format
If your function uses the same format for its functions as Scanpy (`function(adata: AnnData, **kwargs)`), you can simplify your node definition:
```Python3
from your_package import your_function
class MyNode(PipelineNode):
    important_parameters = ["param1"]
    
    def __init__(self,
                 param1: str,
                 param2: bool):
        self.function = your_function
        super().__init__()
        self.store_vars_as_parameters(**vars())
```
That's it! The default run() method will pass the data and parameters to your function, and your node is complete!

### Informing the validator: Interaction and InteractionList
If your node uses AnnData objects for inputs/outputs, you can take advantage of pipeline validation to ensure that your node's requirements are met. This is done via `Interaction` and `InteractionList` objects. An `Interaction` is defined using attributes of AnnData: obs, var, obsm, etc. These are used to determine what fields your function assumes will be defined in order to function correctly. For example:
```Python3
from pscs_api import Interaction
example_interaction = Interaction(obs=["leiden"])
example_interaction_list = InteractionList(example_interaction)
```
would be used to specify that the "leiden" value for the "obs" field of an AnnData object. We can specify this requirement using the `requirements` class variable:

```Python3
class MyNode(PipelineNode):
    important_parameters = ["param1"]
    requirements = InteractionList(obs=["leiden"])

    # etc.
```
The validator will now be able to verify that the input data sent to your node meets its requirements. Similarly, you can specify what information is added to the AnnData object by your node using the `effects` class variable. For example, if your node adds the `coverage` column to `var`, you would specify it as follows:

```Python3
class MyNode(PipelineNode):
    important_parameters = ["param1"]
    requirements = InteractionList(obs=["leiden"])
    effects = InteractionList(var=["coverage"])

    # etc.
```

### Node documentation
You can provide users with documentation to your node, including links to online documentation. This is simplified if your code already has the relevant documentation:
```Python3
from your_package import your_function
class MyNode(PipelineNode):
    # [...]
    function = your_function
    doc_url = "https://myproject.readthedocs.io/"
    __doc__ = PipelineNode.set_doc(function, doc_url)

    # etc.
```

### Advanced use: istr and InteractionList operations.
Some functions produce fields based on the value of certain parameters. For example, many of Scanpy's own functions have a `key_added` argument that specify the name of the key to be added to the AnnData object. The PSCS API supports this for requirements/effects through the use of `istr`, which examine the parameter value of the current node to inform its final value. The following node would require that the value of `param1` is a defined column in the `AnnData.obs` object, and that it will add the value of `param2` as a column in the `AnnData.var` object:
```Python3
class MyNode(PipelineNode):
    important_parameters = ["param1", "param2"]
    requirements = InteractionList(obs=[istr("param1")])
    effects = InteractionList(var=[istr("param2")])

    # [...]
```

Lastly, nodes can have different conditions, where it would suffice for any one of them to be satisfied. Although we discourage this because it makes code less readable, you can achieve this using operations on `InteractionList` objects. For example:
```Python3
ilist0 = InteractionList(Interaction(obs=["groups"]), Interaction(obs=["leiden"]), Interaction(obs=["louvain"]))
```
specifies that either `groups` OR `leiden` OR `louvain` must be specified. If your code also requires `neighbors` to be defined, then you could add it to every `Interaction` in the list, or you can multiply them together:
```Python3
ilist1 = ilist0 * InteractionList(uns=["neighbors"])
```

## Reporting Issues  
Issues can be reported via the Issues tab on GitHub.
