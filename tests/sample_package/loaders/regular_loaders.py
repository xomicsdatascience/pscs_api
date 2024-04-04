from pscs_api.base import InputNode
from typing import Collection


class SlowLoader(InputNode):
    def __init__(self,
                 example: Collection[str],
                 example2: Collection[str] = ("thing",)):
        """For testing."""
        super().__init__()
        self.parameters = self.store_vars_as_parameters(**vars())
        return

    def run(self):
        print("Success!")
        return
