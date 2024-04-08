from pscs_api.base import PipelineNode
from typing import Collection


class TopProc(PipelineNode):
    def __init__(self,
                 example: Collection[str]):
        """For testing."""
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        return

class TiedForSecondProc(PipelineNode):
    def __init__(self,
                 sample: Collection[bool]):
        """Also for testing."""
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        return

class HasSameNameButDifferentParents(PipelineNode):
    def __init__(self,
                 name: str):
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        return