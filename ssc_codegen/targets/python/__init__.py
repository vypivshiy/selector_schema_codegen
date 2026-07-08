"""Configured Python visitor instances (public API)."""

from ssc_codegen.targets.python.html_libs.bs4 import Bs4DomSpelling
from ssc_codegen.targets.python.html_libs.lxml import LxmlDomSpelling
from ssc_codegen.targets.python.html_libs.parsel import ParselDomSpelling
from ssc_codegen.targets.python.html_libs.slax import SlaxDomSpelling
from ssc_codegen.targets.python.visitor import PythonVisitor

PY_BS4_CONVERTER = PythonVisitor(dom_spelling_cls=Bs4DomSpelling)
PY_LXML_CONVERTER = PythonVisitor(dom_spelling_cls=LxmlDomSpelling)
PY_PARSEL_CONVERTER = PythonVisitor(dom_spelling_cls=ParselDomSpelling)
PY_SLAX_CONVERTER = PythonVisitor(dom_spelling_cls=SlaxDomSpelling)
