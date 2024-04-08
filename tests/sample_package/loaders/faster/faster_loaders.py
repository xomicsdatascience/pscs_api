# from .....pscs_api.base import InputNode
from pscs_api.base import InputNode
from typing import Collection


class FasterLoader(InputNode):
    def __init__(self,
                 example: Collection[str]):
        """For testing."""
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        print("Faster loader success!")
        return
