#!/usr/bin/env python3

import os
import shutil
import unittest
import doxycheck
import subprocess

VTR_REPOSITORY = "https://github.com/verilog-to-routing/vtr-verilog-to-routing"
VTR_DIR = os.path.join(os.path.dirname(__file__), "build", "vtr-verilog-to-routing")  # Noqa: E501


class TestVTR(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean previous test
        shutil.rmtree(VTR_DIR, ignore_errors=True)

        # Clone vtr repository
        os.makedirs(VTR_DIR, exist_ok=True)
        cmd = "git clone {repository} {directory}".format(
            repository=VTR_REPOSITORY,
            directory=VTR_DIR
        )
        subprocess.run(cmd, shell=True)

    def test_vpr(self):
        SRC_DIR = os.path.join(VTR_DIR, "vpr/src")

        inputs = list()
        inputs.append(SRC_DIR)
        doxy = doxycheck.Doxycheck(inputs)
        doxy.check(doxygen_html=True, sphinx_html=True, no_browser=True)

    def test_ace2(self):
        SRC_DIR = os.path.join(VTR_DIR, "ace2")

        inputs = list()
        inputs.append(SRC_DIR)
        doxy = doxycheck.Doxycheck(inputs)
        doxy.check(doxygen_html=True, sphinx_html=True, no_browser=True)


if __name__ == '__main__':
    unittest.main()
