import ast

from uc_functions.visitors import UnresolvedNamesFinder


def test_visit_import_single():
    code = "import os"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "os" in finder.defined_names


def test_visit_import_multiple():
    code = "import os\nimport sys"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "os" in finder.defined_names
    assert "sys" in finder.defined_names


def test_visit_import_from_single():
    code = "from os import path"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "path" in finder.defined_names


def test_visit_import_from_multiple():
    code = "from os import path\nfrom sys import argv"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "path" in finder.defined_names
    assert "argv" in finder.defined_names


def test_visit_function_def():
    code = "def foo(arg1, arg2): pass"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "foo" in finder.defined_names
    assert "arg1" in finder.defined_names
    assert "arg2" in finder.defined_names


def test_visit_class_def():
    code = "class Foo: pass"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "Foo" in finder.defined_names


def test_visit_assign():
    code = "x = 1"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "x" in finder.defined_names


def test_visit_name_load():
    code = "print(x)"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "x" in finder.used_names


def test_visit_name_store():
    code = "x = 1"
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    assert "x" in finder.defined_names


def test_get_undefined_names():
    code = """
x = 1
print(y)
"""
    tree = ast.parse(code)
    finder = UnresolvedNamesFinder()
    finder.visit(tree)
    undefined_names = finder.get_undefined_names()
    assert "y" in undefined_names
    assert "x" not in undefined_names
