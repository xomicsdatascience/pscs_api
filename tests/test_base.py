import unittest
from typing import Optional, Collection
import io
import contextlib
from pscs_api.base import Pipeline, PipelineNode, InputNode, OutputNode


class TestBase(unittest.TestCase):
    def test_inputnode(self):
        inp = SampleInput(transpose=True)
        self.assertTrue(inp.parameters["transpose"])
        inp.run()
        self.assertEqual(inp.result, [1,2,3])
        return

    def test_pipelinenode(self):
        # PipelineNode is an abstract class; need to define class to inherit it
        inp = SampleInput()
        pnode = SampleNodeTriple()
        inp.connect_to_output(pnode)
        inp.run()
        pnode.run()
        self.assertEqual(pnode.result, [3, 6, 9])
        return

    def test_outputnode(self):
        inp = SampleInput()
        pnode = SampleNodeTriple()
        outp = SampleOutput()
        inp.connect_to_output(pnode)
        outp.connect_to_input(pnode)
        inp.run()
        pnode.run()
        # Output nodes shouldn't be expected to store anything; they report, save to disk, etc.
        out_str = io.StringIO()
        with contextlib.redirect_stdout(out_str):  # grab stdout
            outp.run()
        self.assertTrue("[3, 6, 9]" in out_str.getvalue())
        return

class SampleInput(InputNode):
    important_parameters = ["transpose"]

    def __init__(self,
                 transpose: bool = False):
        super(SampleInput, self).__init__()
        self.store_vars_as_parameters(**vars())
        return

    def run(self):
        data = [1, 2, 3]  # This would normally be fetched from a file
        self._terminate(data)
        return


class SampleNodeTriple(PipelineNode):
    important_parameters = ["plot"]

    def __init__(self,
                 plot: str = "eg",
                 arg1: Optional[str] = None,
                 arg2: Collection[int] = (1, 2, 3),
                 arg3: bool = False):
        super().__init__()
        self.store_vars_as_parameters(**vars(), arg4=4)
        return

    def run(self):
        data = self._previous[0].result
        node_output = [d*3 for d in data]
        self._terminate(node_output)
        return


class SampleOutput(OutputNode):
    def __init__(self,
                 out_path: Optional[str] = None):
        super().__init__()
        self.store_vars_as_parameters(**vars())
        return

    def run(self):
        data = self._previous[0].result
        print(data)
        self._terminate(data)
        return
