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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig()


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


class DoxycheckError(Exception):
    pass


class Doxycheck:

    C_EXTS = [".c", ".cc", ".cxx", ".cpp", ".c++", ".h", ".hh", ".hxx", ".hpp", ".h++"]  # Noqa: E501
    DOXYGEN_C_CONFIG = {
        "FULL_PATH_NAMES": "NO",
        "OPTIMIZE_OUTPUT_FOR_C": "YES",
        "RECURSIVE": "YES",

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
            assert os.path.exists(f), "File {} does not exist!".format(f)

        # Create temporary output directory

        self.outdir = self._mkdtemp()
        logger.debug("Creating output directory: {}".format(self.outdir))

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

    def _get_default_doxygen_config(self, field=None):
        """
        Used to obtain Doxygen default configuration.

        Args:
            field: doxyfile value that should be returned

        Returns:
            If "field is None returns a dictionary with default
            doxyfile contents
            If "field" is specified returns a chosen configuration value.
        """

        DEFAULT_DOXYFILE_PATH = os.path.join(self.outdir, "default_doxyfile")

        cmd = "doxygen -s -g {doxyfile}".format(doxyfile=DEFAULT_DOXYFILE_PATH)
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

        config_parser = ConfigParser()
        config = config_parser.load_configuration(DEFAULT_DOXYFILE_PATH)

        if field is not None and field not in config:
            raise DoxycheckError('Config value "{}" not in default doxyfile'.format(field))  # Noqa: E501

        if field is None:
            return config
        else:
            return config[field]

    def _update_input_dict(self, fname):
        assert isinstance(fname, list)

        self._resolve_explicit_inputs(fname)
        self._resolve_inputs_recursively()

        # from pprint import pformat
        # logger.debug("Printing inputs...")
        # logger.debug(pformat(self.inputs))

    def _resolve_explicit_inputs(self, fname):

        files = []
        dirs = []
        for f in fname:
            _, ext = os.path.splitext(f)

            if os.path.isfile(f) and ext in Doxycheck.C_EXTS:
                files.append(f)
            elif os.path.isdir(f):
                dirs.append(f)
            else:
                assert False, "Unknown type of {}".format(f)

        logger.debug("Adding directory: {}".format("."))
        self.inputs.update({".": {
             "in": ".",
             "out": self.doxygen_out["srcdir"],
             "files": list()
        }})

        for d in dirs:
            name = os.path.basename(d)

            inpath = os.path.realpath(d)
            outpath = os.path.join(self.doxygen_out["srcdir"], name)

            logger.debug("Adding directory: {}".format(name))
            self.inputs.update({name: {
                "in": inpath,
                "out": outpath,
                "files": list()
            }})

        for f in files:
            name = os.path.basename(d)

            inpath = os.path.realpath(d)
            outpath = os.path.join(self.doxygen_out["srcdir"], name)

            logger.debug("Adding file: {}".format(inpath))
            file_dict = {
                "in": inpath,
                "out": outpath,
            }

            self.inputs["."]["files"].append(file_dict)

    def _resolve_inputs_recursively(self):

        recursive_dirs = dict()

        for root_name, path_dict in self.inputs.items():
            root_inpath = path_dict["in"]
            root_outpath = path_dict["out"]

            for root, dirs, files in os.walk(root_inpath):
                relpath = os.path.relpath(root, start=root_inpath)

                for d in dirs:
                    d_inpath = os.path.join(root, d)
                    d_outpath = os.path.realpath(os.path.join(root_outpath, relpath, d))  # noqa: E501
                    d_relpath = os.path.relpath(d_inpath, start=root_inpath)  # noqa: E501
                    d_name = os.path.join(root_name, d_relpath)

                    logger.debug("Adding directory: {}".format(d_name))
                    recursive_dirs.update({d_name: {
                        "in":  d_inpath,
                        "out": d_outpath,
                        "files": list()
                    }})

                for f in files:
                    name, ext = os.path.splitext(f)

                    if ext not in Doxycheck.C_EXTS:
                        logger.debug("Skipping file: {}".format(f))
                        continue

                    f_inpath = os.path.join(root, f)
                    f_outpath = os.path.realpath(os.path.join(root_outpath, relpath, f))  # noqa: E501
                    f_relpath = os.path.relpath(f_inpath, start=root_inpath)  # noqa: E501
                    f_name = os.path.join(root_name, f_relpath)

                    logger.debug("Adding file: {}".format(f_name))
                    file_dict = {
                        "in":  f_inpath,
                        "out": f_outpath
                    }

                    dirname = os.path.dirname(f_name)
                    recursive_dirs[dirname]["files"].append(file_dict)

        self.inputs = {**self.inputs, **recursive_dirs}

    def check(self, doxygen_html, sphinx_html):

        logger.debug("Preparing output Doxygen directories..")

        os.makedirs(self.doxygen_out["srcdir"])
        os.makedirs(self.doxygen_out["builddir"])

        logger.debug("Generating Doxygen output..")

        self._generate_doxygen()
        self._show_doxygen_warnings()

        if doxygen_html:
            self._show_doxygen_html()

        #if sphinx_html:
        #     self._generate_sphinx()
        #     self._show_sphinx_html()
        #     self._show_sphinx_warnings()

        if not sphinx_html and not doxygen_html:
            self._clear()

    def _mkdtemp(self):
        return tempfile.mkdtemp(prefix=Doxycheck.tempdir_prefix)

    def _clear(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _generate_doxygen(self):
        # Copy source file and add doxygen header to ensure that file
        # index will be generated

        # Create dirs

        for name, path_dict in self.dir_in.items():
            outpath = path_dict["out"]
            os.mkdir(outpath)

        # Copy files

        for name, path_dict in self.file_in.items():
            inpath = path_dict["in"]
            outpath = path_dict["out"]

            with open(inpath, "r") as f_in, open(outpath, "w") as f_out:
                f_out.write("/** @file */")
                f_out.write(f_in.read())

        # Complete config

        config = Doxycheck.DOXYGEN_C_CONFIG
        config["INPUT"] = self.doxygen_out["srcdir"]
        config["OUTPUT_DIRECTORY"] = self.doxygen_out["builddir"]
        config["WARN_LOGFILE"] = self.doxygen_out["warnfile"]
        config["PROJECT_NAME"] = "Doxygen"

        # Save Doxygen configuration

        doxyfile_tmpfile = self.doxygen_out["doxyfile"]
        config_parser = ConfigParser()
        config_parser.store_configuration(config, doxyfile_tmpfile)

        # Build doxygen documentation

        doxy_builder = Generator(doxyfile_tmpfile)
        doxy_builder.build(generate_zip=True, clean=False)

    def _generate_sphinx(self):
        # Prepare Sphinx directories

        os.mkdir(self.sphinx_out["srcdir"])
        os.mkdir(self.sphinx_out["outdir"])
        os.mkdir(self.sphinx_out["doctreedir"])

        # Create minimal config
        sphinx_conf_file = os.path.join(self.sphinx_src_dir, "conf.py")
        sphinx_conf_content = """
project = 'Doxygen'
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
        with open(self.doxygen_out["warnfile"]) as wf:
            for line in wf.readlines():
                tmp = line.replace("{}/".format(self.doxygen_out["srcdir"]), "")  # Noqa: E501
                color_print(tmp, color="YELLOW", end="")

    def _show_sphinx_warnings(self):
        if os.path.getsize(self.sphinx_warn_file) > 0:
            with open(self.sphinx_warn_file) as wf:
                print(wf.read())

    def _show_doxygen_html(self):

        if len(self.dir_in) == 0 and len(self.file_in) == 1:
            file_name = os.path.basename(list(self.file_in.values())[0])
            name, ext = os.path.splitext(file_name)
            html_name = "html/{}_8{}.html".format(name, ext[1:])
        else:
            html_name = "html/files.html"

        html_file = os.path.join(self.doxygen_out["builddir"], html_name)
        webbrowser.open(html_file)

    def _show_sphinx_html(self):
        html_file = os.path.join(self.sphinx_out_dir, "index.html")
        webbrowser.open(html_file)


def main():
    parser = argparse.ArgumentParser(description="Test doxygen code comments using doxygen/sphinx+breathe")  # noqa: E501
    parser.add_argument("file", nargs='+', help="document to validate")
    parser.add_argument("--doxygen-html", action="store_true", help="show Doxygen html")  # noqa: E501
    parser.add_argument("--sphinx-html", action="store_true", help="show Sphinx html")  # noqa: E501
    args = parser.parse_args()

    doxycheck = Doxycheck(args.file)
    #doxycheck.check(args.doxygen_html, args.sphinx_html)


if __name__ == "__main__":
    main()
