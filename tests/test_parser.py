import unittest
from typing import Optional, Collection
from pscs_api.node_parser import parse_package
import tempfile
import os


class TestNodeParser(unittest.TestCase):
    def test_simplepackage(self):
        tmp_f, tmp_name = tempfile.mkstemp(suffix="pscsapitest.json")
        cur_dir = os.path.dirname(__file__)
        parse_package(tmp_name,
                      parse_directory=os.path.join(cur_dir, "sample_package", "loaders", "faster"),
                      package_name="api_test")
        return

    def test_parsepackage(self):
        tmp_f, tmp_name = tempfile.mkstemp(suffix="pscsapitest.json")
        cur_dir = os.path.dirname(__file__)
        parse_package(tmp_name,
                      parse_directory=os.path.join(cur_dir, "sample_package"),
                      package_name="sample_package",
                      display_name="Sample package")
        return
