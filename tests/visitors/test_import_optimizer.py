import ast

from uc_functions.visitors import ImportOptimizer


def test_visit_import_single():
    code = "import os"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert "os" in optimizer.imported_names


def test_visit_import_multiple():
    code = "import os\nimport sys"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert "os" in optimizer.imported_names
    assert "sys" in optimizer.imported_names


def test_visit_import_duplicate():
    code = "import os\nimport os"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert len(optimizer.seen_imports) == 1


def test_visit_import_from_single():
    code = "from os import path"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert "path" in optimizer.imported_names


def test_visit_import_from_multiple():
    code = "from os import path\nfrom sys import argv"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert "path" in optimizer.imported_names
    assert "argv" in optimizer.imported_names


def test_visit_import_from_duplicate():
    code = "from os import path\nfrom os import path"
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.visit(tree)
    assert len(optimizer.seen_imports) == 1


def test_optimize_imports_combined():
    code = """
import os
from sys import argv
"""
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.optimize_imports(tree)
    assert "os" in optimizer.imported_names
    assert "argv" in optimizer.imported_names


def test_optimize_imports_unused():
    code = """
import os
import sys
x = 1
"""
    tree = ast.parse(code)
    optimizer = ImportOptimizer()
    optimizer.optimize_imports(tree)
    final_code = ast.unparse(tree)
    assert final_code.strip() == "x = 1"
