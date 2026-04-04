# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath("source"))
sys.path.insert(1, str(Path(__file__).parent))
sys.path.insert(2, str(Path(__file__).parent.parent))

# -- Project information -----------------------------------------------------

project = "PyBreeze"
copyright = "2020 ~ Now, JE-Chen"
author = "JE-Chen"

# -- General configuration ---------------------------------------------------

extensions = []

templates_path = ["_templates"]

language = "en"

exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"

html_static_path = ["_static"]
