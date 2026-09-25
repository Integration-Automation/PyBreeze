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
# ``project_copyright`` is Sphinx's official alias for ``copyright`` (3.5+),
# provided so a conf.py need not shadow the builtin of that name.
project_copyright = "2020 ~ Now, JE-Chen"
author = "JE-Chen"

# -- General configuration ---------------------------------------------------

extensions = []

language = "en"

exclude_patterns = []

# -- Options for HTML output -------------------------------------------------

html_theme = "sphinx_rtd_theme"

# -- Options for LaTeX (PDF) output -------------------------------------------

# Half of the guide is Traditional Chinese, which pdflatex cannot set: the PDF
# Read the Docs built had every Chinese character missing. xelatex sets it with
# xeCJK and the Noto CJK TC fonts, which Read the Docs' build image has
# (fonts-noto-cjk); ctex's own fonts leave out some Traditional characters.
latex_engine = "xelatex"
latex_use_xindy = False
latex_elements = {
    "preamble": "\n".join((
        r"\usepackage{xeCJK}",
        r"\setCJKmainfont{Noto Serif CJK TC}",
        r"\setCJKsansfont{Noto Sans CJK TC}",
        r"\setCJKmonofont{Noto Sans Mono CJK TC}",
    )),
}
