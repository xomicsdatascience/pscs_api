from pscs_api.base import PipelineNode
from typing import Collection


class BottomProc(PipelineNode):
    def __init__(self,
                 example: Collection[str]):
        """For testing."""
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        return


class HasSameNameButDifferentParents(PipelineNode):
    def __init__(self,
                 bubbles: str):
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        return