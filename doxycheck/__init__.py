#!/usr/bin/env python3

import os
import parse
import shutil
import tempfile
import argparse
import webbrowser

from sphinx.application import Sphinx
from sphinx.util.docutils import docutils_namespace
from doxygen import ConfigParser, Generator


def color_print(text, color=None, bold=False, underline=False, **kwargs):
    MODIFIERS = {
        "PURPLE": '\033[95m',
        "CYAN": '\033[96m',
        "DARKCYAN": '\033[36m',
        "BLUE": '\033[94m',
        "GREEN": '\033[92m',
        "YELLOW": '\033[93m',
        "RED": '\033[91m',
        "BOLD": '\033[1m',
        "UNDERLINE": '\033[4m',
        "END": '\033[0m',
    }

    modifier = ""

    if color in MODIFIERS.keys():
        modifier += MODIFIERS[color]

    if bold:
        modifier += MODIFIERS["BOLD"]

    if underline:
        modifier += MODIFIERS["UNDERLINE"]

    endmodifier = MODIFIERS["END"]
    print(modifier, text, endmodifier, **kwargs)


class Doxycheck:

    DOXYGEN_C_CONFIG = {
        "FULL_PATH_NAMES": "NO",
        "OPTIMIZE_OUTPUT_FOR_C": "YES",

        "GENERATE_HTML": "YES",
        "GENERATE_XML": "YES",
        "GENERATE_LATEX": "NO",

        "WARNINGS": "YES",
        "WARN_IF_UNDOCUMENTED": "YES",
        "WARN_IF_DOC_ERROR": "YES",
        "WARN_NO_PARAMDOC": "YES",

        "EXTRACT_ALL": "NO",
        "EXTRACT_PRIVATE": "YES",
        "EXTRACT_PRIV_VIRTUAL": "YES",
        "EXTRACT_PACKAGE": "YES",
        "EXTRACT_STATIC": "YES",
        "EXTRACT_LOCAL_CLASSES": "YES",
        "EXTRACT_LOCAL_METHODS": "YES",
        "EXTRACT_ANON_NSPACES": "YES",

        "INPUT": None,
        "OUTPUT_DIRECTORY": None,
        "WARN_LOGFILE": None,
        "PROJECT_NAME": None
    }

    tempdir_prefix = "doxycheck_"

    def __init__(self, fname):
        assert os.path.exists(fname)

        self.fname = os.path.realpath(fname)
        self.fbasename = os.path.basename(fname)

        self.output_dir = self._mkdtemp()

        # Doxygen dirs

        self.output_src_dir = os.path.join(self.output_dir, "src")
        self.output_src_file = os.path.join(self.output_src_dir, self.fbasename)  # noqa: E501
        self.output_build_dir = os.path.join(self.output_dir, "build")
        self.output_warn_file = os.path.join(self.output_dir, "warn.log")
        self.output_doxy_file = os.path.join(self.output_dir, "doxyfile")

        # Sphinx dirs

        self.sphinx_src_dir = os.path.join(self.output_dir, "sphinx")
        self.sphinx_out_dir = os.path.join(self.output_build_dir, "sphinx")
        self.sphinx_doctree_dir = os.path.join(self.sphinx_out_dir, "doctrees")
        self.sphinx_log_file = os.path.join(self.sphinx_out_dir, "sphinx.log")
        self.sphinx_warn_file = os.path.join(self.sphinx_out_dir, "warn.log")

    def check(self, doxygen_html, sphinx_html):

        # Prepare output directory tree

        os.mkdir(self.output_src_dir)
        os.mkdir(self.output_build_dir)

        # Generate doxygen output and show warnings

        self._generate_doxygen()
        self._show_doxygen_warnings()

        if doxygen_html:
            self._show_doxygen_html()

        if sphinx_html:
            self._generate_sphinx()
            self._show_sphinx_html()
            self._show_sphinx_warnings()

        if not sphinx_html and not doxygen_html:
            self._clear()

    def _mkdtemp(self):
        return tempfile.mkdtemp(prefix=Doxycheck.tempdir_prefix)

    def _clear(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _generate_doxygen(self):
        assert os.path.exists(self.fname)

        # Copy source file and add doxygen header to ensure that file
        # index will be generated

        with open(self.output_src_file, "a") as src:
            src.write("/** @file */")
            with open(self.fname) as inp_file:
                src.write(inp_file.read())

        # Complete config

        config = Doxycheck.DOXYGEN_C_CONFIG
        config["INPUT"] = self.output_src_dir
        config["OUTPUT_DIRECTORY"] = self.output_build_dir
        config["WARN_LOGFILE"] = self.output_warn_file
        config["PROJECT_NAME"] = self.fbasename

        # Save Doxygen configuration

        doxyfile_tmpfile = self.output_doxy_file
        config_parser = ConfigParser()
        config_parser.store_configuration(config, doxyfile_tmpfile)

        # Build doxygen documentation

        doxy_builder = Generator(doxyfile_tmpfile)
        doxy_builder.build(generate_zip=True, clean=False)

    def _generate_sphinx(self):
        # Prepare Sphinx directories

        os.mkdir(self.sphinx_src_dir)
        os.mkdir(self.sphinx_out_dir)
        os.mkdir(self.sphinx_doctree_dir)

        # Create minimal config
        sphinx_conf_file = os.path.join(self.sphinx_src_dir, "conf.py")
        sphinx_conf_content = """
project = 'name'
extensions = ['breathe']
html_theme = 'sphinx_rtd_theme'

breathe_projects = {{ 'default': '{doxygen_xml_file}' }}
breathe_default_project = 'default'
""".format(doxygen_xml_file=os.path.join(self.output_build_dir, "xml"))

        with open(sphinx_conf_file, "w") as sf:
            sf.write(sphinx_conf_content)

        # Create basic RST file

        rst_file = os.path.join(self.sphinx_src_dir, "index.rst")
        rst_file_content = """
{file}
===============================================================================

.. doxygenfile:: {file}
""".format(file=self.fbasename)

        with open(rst_file, "w") as rf:
            rf.write(rst_file_content)

        with docutils_namespace(), \
             open(self.sphinx_log_file, "w") as lf, \
             open(self.sphinx_warn_file, "w") as wf:

            app = Sphinx(buildername="html",
                         srcdir=self.sphinx_src_dir,
                         confdir=self.sphinx_src_dir,
                         outdir=self.sphinx_out_dir,
                         doctreedir=self.sphinx_doctree_dir,
                         status=lf,
                         warning=wf)
            app.build()

    def _show_doxygen_warnings(self):
        with open(self.output_warn_file) as wf:
            for line in wf.readlines():
                result = parse.parse("{file}:{line}: {type}: {text}", line)

                color = "YELLOW" if result["type"] == "warning" else "RED"
                msg_type = result["type"].upper()
                identifier = "{type} [{file}:{line}]:".format(
                    type=msg_type,
                    file=os.path.basename(result["file"]),
                    line=result["line"],
                )
                color_print(identifier, bold=True, color=color, end='')
                color_print(result["text"], color=color)

    def _show_sphinx_warnings(self):
        if os.path.getsize(self.sphinx_warn_file) > 0:
            with open(self.sphinx_warn_file) as wf:
                print(wf.read())

    def _show_doxygen_html(self):
        name, ext = os.path.splitext(self.fbasename)
        html_name = "build/html/{}_8{}.html".format(name, ext[1:])
        html_file = os.path.join(self.output_dir, html_name)

        webbrowser.open(html_file)

    def _show_sphinx_html(self):
        html_file = os.path.join(self.sphinx_out_dir, "index.html")
        webbrowser.open(html_file)


def main():
    parser = argparse.ArgumentParser(description="Test doxygen code comments using doxygen/sphinx+breathe")  # noqa: E501
    parser.add_argument("file", help="document to validate")
    parser.add_argument("--doxygen-html", action="store_true", help="show Doxygen html")  # noqa: E501
    parser.add_argument("--sphinx-html", action="store_true", help="show Sphinx html")  # noqa: E501
    args = parser.parse_args()

    doxycheck = Doxycheck(args.file)
    doxycheck.check(args.doxygen_html, args.sphinx_html)


if __name__ == "__main__":
    main()
