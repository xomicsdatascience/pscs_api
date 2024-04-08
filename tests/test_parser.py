import unittest
from typing import Optional, Collection
from pscs_api.node_parser import parse_package, parse_package2
import tempfile
import os


class TestNodeParser(unittest.TestCase):
    def test_simplepackage(self):
        tmp_f, tmp_name = tempfile.mkstemp(suffix="pscsapitest.json")
        cur_dir = os.path.dirname(__file__)
        parse_package(tmp_name,
                      parse_directory=os.path.join(cur_dir, "sample_package", "loaders", "faster"),
                      exclude_files=["__init__.py"],
                      package_name="api_test",
                      overwrite=True)
        return

    def test_parsepackage(self):
        tmp_f, tmp_name = tempfile.mkstemp(suffix="pscsapitest.json")
        cur_dir = os.path.dirname(__file__)
        parse_package2(tmp_name,
                      parse_directory=os.path.join(cur_dir, "sample_package"),
                      package_name="sample_package",
                       display_package_name="Sample package",
                      overwrite=True)
        return
