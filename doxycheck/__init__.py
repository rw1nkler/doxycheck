#!/usr/bin/env python3

import os
import shutil
import logging
import tempfile
import argparse
import subprocess
import webbrowser

from sphinx.application import Sphinx
from sphinx.util.docutils import docutils_namespace
from doxygen import ConfigParser, Generator
from colorama import Fore, init as colorama_init

logger = logging.getLogger(__name__)


class DoxycheckError(Exception):
    pass


class Doxycheck:
    C_EXTS = [".c", ".cc", ".cxx", ".cpp", ".c++", ".h", ".hh", ".hxx", ".hpp", ".h++"]  # Noqa: E501
    DOXYGEN_C_CONFIG = {
        "FULL_PATH_NAMES": "NO",
        "OPTIMIZE_OUTPUT_FOR_C": "YES",
        "RECURSIVE": "YES",
        "REPEAT_BRIEF": "NO",

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
        assert isinstance(fname, list)
        for f in fname:
            assert os.path.exists(f), "Input {} does not exist!".format(f)

        # Create temporary output directory

        self.outdir = self._mkdtemp()
        logger.info("Creating output directory: {}".format(self.outdir))

        # Generated doxygen output dirs / files

        self.doxygen_out = {
            "srcdir":   os.path.join(self.outdir, "src"),
            "builddir": os.path.join(self.outdir, "build", "doxygen"),
            "warnfile": os.path.join(self.outdir, "warn.log"),
            "doxyfile": os.path.join(self.outdir, "doxyfile")
        }

        # Generated sphinx output dirs / files

        self.sphinx_out = {
            "srcdir":     os.path.join(self.outdir, "sphinx"),
            "outdir":     os.path.join(self.outdir, "build", "sphinx"),
            "doctreedir": os.path.join(self.outdir, "build", "doctrees"),
            "logfile":    os.path.join(self.outdir, "build", "sphinx.log"),
            "warnfile":   os.path.join(self.outdir, "build", "warn.log")
        }

        # Analyze inputs

        logger.debug("Searching for input files...")

        self.inputs = dict()
        self._update_input_dict(fname)

    def _update_input_dict(self, fname):
        """Update the inputs dictionary with explicit sources and those found recursively"""

        assert isinstance(fname, list)

        self._resolve_explicit_inputs(fname)
        self._resolve_inputs_recursively()

        if logger.getEffectiveLevel() == logging.DEBUG:
            from pprint import pformat
            logger.debug("Printing inputs...")
            logger.debug(pformat(self.inputs))

    def _resolve_explicit_inputs(self, fname):
        """Update the inputs dictionary with explicit sources"""

        files = []
        dirs = []
        for f in fname:
            _, ext = os.path.splitext(f)

            if os.path.isfile(f) and ext in Doxycheck.C_EXTS:
                files.append(f)
            elif os.path.isdir(f):
                dirs.append(f)
            else:
                assert False, "Unknown type of input: {}".format(f)

        # Always add "." directory as a place for explicit files
        # from the input list

        logger.info("Adding directory: {}".format("."))
        self.inputs.update({".": {
             "in": ".",
             "out": self.doxygen_out["srcdir"],
             "files": list()
        }})

        # Add all the directories

        for d in dirs:
            name = os.path.basename(d)

            inpath = os.path.realpath(d)
            outpath = os.path.join(self.doxygen_out["srcdir"], name)

            logger.info("Adding directory: {}".format(name))
            dir_dict = {
                "in": inpath,
                "out": outpath,
                "files": list()
            }
            self.inputs.update({name: dir_dict})

        # Add all the files from the input list to the inputs dictionary
        # The files provided as an input are associated with the "." output directory

        for f in files:
            name = os.path.basename(f)

            inpath = os.path.realpath(f)
            outpath = os.path.join(self.doxygen_out["srcdir"], name)

            logger.info("Adding file: {}".format(inpath))
            file_dict = {
                "in": inpath,
                "out": outpath,
            }
            self.inputs["."]["files"].append(file_dict)

    def _resolve_inputs_recursively(self):
        """Update inputs dictionary with the files found recursively in the input directories"""

        recursive_dirs = {**self.inputs}

        for root_name, path_dict in self.inputs.items():
            root_inpath = path_dict["in"]
            root_outpath = path_dict["out"]

            # Skip adding files to "." output directory.
            # This is a place for the explicit sources

            if root_inpath == ".":
                continue

            # Add files from the input directories

            for root, dirs, files in os.walk(root_inpath):
                relpath = os.path.relpath(root, start=root_inpath)

                for d in dirs:
                    d_inpath = os.path.join(root, d)
                    d_outpath = os.path.realpath(os.path.join(root_outpath, relpath, d))  # noqa: E501
                    d_relpath = os.path.relpath(d_inpath, start=root_inpath)  # noqa: E501
                    d_name = os.path.join(root_name, d_relpath)

                    logger.info("Adding directory recursively: {}".format(d_name))  # noqa: E501
                    dir_dict = {
                        "in":  d_inpath,
                        "out": d_outpath,
                        "files": list()
                    }
                    recursive_dirs.update({d_name: dir_dict})

                for f in files:
                    name, ext = os.path.splitext(f)

                    if ext not in Doxycheck.C_EXTS:
                        logger.debug("Skipping file: {}".format(f))
                        continue

                    f_inpath = os.path.join(root, f)
                    f_outpath = os.path.realpath(os.path.join(root_outpath, relpath, f))  # noqa: E501
                    f_relpath = os.path.relpath(f_inpath, start=root_inpath)  # noqa: E501
                    f_name = os.path.join(root_name, f_relpath)

                    logger.info("Adding file recursively: {}".format(f_name))
                    file_dict = {
                        "in":  f_inpath,
                        "out": f_outpath
                    }
                    dirname = os.path.dirname(f_name)
                    recursive_dirs[dirname]["files"].append(file_dict)

        # Update the main inputs dictionary

        self.inputs = {**self.inputs, **recursive_dirs}

    def check(self, doxygen_html, sphinx_html):
        """Main function of Doxycheck class, called to validate code comments"""

        logger.debug("Preparing output Doxygen directories..")

        os.makedirs(self.doxygen_out["srcdir"])
        os.makedirs(self.doxygen_out["builddir"])

        logger.debug("Generating Doxygen output..")

        self._generate_doxygen()
        self._print_doxygen_warnings()

        if doxygen_html:
            self._show_doxygen_html()

        if sphinx_html:
            self._generate_sphinx()
            self._show_sphinx_html()
            self._print_sphinx_warnings()

        # Remove the temporary directory only if it is not used by the browser

        if not sphinx_html and not doxygen_html:
            self._clear()

    def _mkdtemp(self):
        """Create a temporary directory for Doxycheck output"""

        return tempfile.mkdtemp(prefix=Doxycheck.tempdir_prefix)

    def _clear(self):
        """Remove the Doxycheck temporary directory"""

        shutil.rmtree(self.outdir, ignore_errors=True)

    def _generate_doxygen(self):
        """Generate doxygen XML and HTML output"""

        # Create Doxygen output directories

        for directory in self.inputs.keys():
            out_dir = self.inputs[directory]["out"]
            os.makedirs(out_dir, exist_ok=True)

            # Copy all the files adding doxygen file header to obtain
            # detailed warnings

            files_list = self.inputs[directory]["files"]
            for f in files_list:
                with open(f["in"], "r") as f_in, open(f["out"], "w") as f_out:
                    f_out.write("/** @file */")
                    f_out.write(f_in.read())

        # Complete default Doxygen config

        config = Doxycheck.DOXYGEN_C_CONFIG
        config["INPUT"] = self.doxygen_out["srcdir"]
        config["OUTPUT_DIRECTORY"] = self.doxygen_out["builddir"]
        config["WARN_LOGFILE"] = self.doxygen_out["warnfile"]
        config["PROJECT_NAME"] = "Doxygen"

        # Save Doxygen configuration

        doxyfile_tmpfile = self.doxygen_out["doxyfile"]
        config_parser = ConfigParser()
        config_parser.store_configuration(config, doxyfile_tmpfile)

        # Build Doxygen documentation (XML and HTML)

        doxy_builder = Generator(doxyfile_tmpfile)
        doxy_builder.build(generate_zip=True, clean=False)

    def _generate_sphinx(self):
        """Generate Sphinx HTML"""

        # Create Sphinx output directories

        os.mkdir(self.sphinx_out["srcdir"])
        os.mkdir(self.sphinx_out["outdir"])
        os.mkdir(self.sphinx_out["doctreedir"])

        # Create a minimal Sphinx config

        sphinx_conf_file = os.path.join(self.sphinx_out["srcdir"], "conf.py")
        sphinx_conf_content = """
project = 'Doxycheck'
extensions = ['breathe']
html_theme = 'sphinx_rtd_theme'

breathe_projects = {{ 'default': '{doxygen_xml_file}' }}
breathe_default_project = 'default'
""".format(doxygen_xml_file=os.path.join(self.doxygen_out["builddir"], "xml"))

        with open(sphinx_conf_file, "w") as sf:
            sf.write(sphinx_conf_content)

        # Create RST files for all the input files

        for directory in self.inputs.keys():
            files_list = self.inputs[directory]["files"]
            for f in files_list:
                file_basename = os.path.basename(f["out"])
                file_path = os.path.join(directory, file_basename)
                file_path_parts = file_path.split(os.sep)
                file_name, ext = os.path.splitext("_".join(file_path_parts))
                rstfile_name = file_name + ".rst"
                rstfile_path = os.path.join(self.sphinx_out["srcdir"], rstfile_name)

                rstfile_content = """{file_name}
===============================================================================

.. doxygenfile:: {srcfile_name}
""".format(file_name=file_path, srcfile_name=file_basename)

                with open(rstfile_path, "w") as rf:
                    rf.write(rstfile_content)

        # Create a main Sphinx index file

        index_rstfile_path = os.path.join(self.sphinx_out["srcdir"], "index.rst")
        index_rstfile_contents = """Doxycheck
===============================================================================

.. toctree::
   :glob:

   *
"""

        with open(index_rstfile_path, "w") as idx:
             idx.write(index_rstfile_contents)

        # Build the Sphinx documentation

        with docutils_namespace(), open(self.sphinx_out["warnfile"], "w") as wf:
            app = Sphinx(buildername="html",
                         srcdir=self.sphinx_out["srcdir"],
                         confdir=self.sphinx_out["srcdir"],
                         outdir=self.sphinx_out["outdir"],
                         doctreedir=self.sphinx_out["doctreedir"],
                         warning=wf)
            app.build()

    def _print_doxygen_warnings(self):
        """Print Doxygen warnings"""

        with open(self.doxygen_out["warnfile"]) as wf:
            for line in wf.readlines():
                tmp = line.replace("{}/".format(self.doxygen_out["srcdir"]), "")  # Noqa: E501
                print(Fore.YELLOW + tmp, end='')
            print("")

    def _print_sphinx_warnings(self):
        """Print Sphinx warnings"""

        if os.path.getsize(self.sphinx_out["warnfile"]) > 0:
            with open(self.sphinx_out["warnfile"]) as wf:
                print(Fore.YELLOW + wf.read())

    def _show_doxygen_html(self):
        """Show generated Doxygen HTML"""

        html_name = "html/files.html"
        html_file = os.path.join(self.doxygen_out["builddir"], html_name)
        webbrowser.open(html_file)

    def _show_sphinx_html(self):
        """Show generated Sphinx HTML"""

        html_file = os.path.join(self.sphinx_out["outdir"], "index.html")
        webbrowser.open(html_file)


def main():
    parser = argparse.ArgumentParser(description="Test doxygen code comments using doxygen/sphinx+breathe")  # noqa: E501
    parser.add_argument("file", nargs='+', help="document to validate")
    parser.add_argument("--doxygen-html", action="store_true", help="show Doxygen html")  # noqa: E501
    parser.add_argument("--sphinx-html", action="store_true", help="show Sphinx html")  # noqa: E501
    args = parser.parse_args()

    colorama_init(autoreset=True)
    logging.basicConfig()

    doxycheck = Doxycheck(args.file)
    doxycheck.check(args.doxygen_html, args.sphinx_html)


if __name__ == "__main__":
    main()
