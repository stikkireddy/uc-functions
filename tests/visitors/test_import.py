import ast
from unittest.mock import patch

from uc_functions.visitors import ImportVisitor, is_library_module


def test_visit_import_single():
    code = "import os"
    tree = ast.parse(code)
    visitor = ImportVisitor()
    visitor.visit(tree)
    assert "import os" in visitor.imports
    assert any(obj.obj_name == "os" for obj in visitor.import_objs)


def test_visit_import_multiple():
    code = "import os\nimport time\n"
    tree = ast.parse(code)
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "import os" in visitor.imports
        assert "import time" in visitor.imports
        assert any(obj.obj_name == "os" for obj in visitor.import_objs)
        assert any(obj.obj_name == "time" for obj in visitor.import_objs)


def test_visit_import_with_alias():
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        code = "import os as operating_system"
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "import os as operating_system" in visitor.imports
        assert any(
            obj.obj_name == "os" and obj.alias == "operating_system"
            for obj in visitor.import_objs
        )


def test_visit_import_from_single():
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        code = "from os import path"
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "from os import path" in visitor.imports
        assert any(
            obj.module_path == "os" and obj.obj_name == "path"
            for obj in visitor.import_objs
        )


def test_visit_import_from_multiple():
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        code = "from os import path\nfrom sys import argv"
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "from os import path" in visitor.imports
        assert "from sys import argv" in visitor.imports
        assert any(
            obj.module_path == "os" and obj.obj_name == "path"
            for obj in visitor.import_objs
        )
        assert any(
            obj.module_path == "sys" and obj.obj_name == "argv"
            for obj in visitor.import_objs
        )


def test_visit_import_from_with_alias():
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        code = "from os import path as p"
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "from os import path" in visitor.imports
        assert any(
            obj.module_path == "os" and obj.obj_name == "path" and obj.alias == "p"
            for obj in visitor.import_objs
        )


def test_combined_imports():
    with patch("uc_functions.visitors.is_library_module", return_value=True):
        code = "import os\nfrom sys import argv"
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)
        assert "import os" in visitor.imports
        assert "from sys import argv" in visitor.imports
        assert any(obj.obj_name == "os" for obj in visitor.import_objs)
        assert any(
            obj.module_path == "sys" and obj.obj_name == "argv"
            for obj in visitor.import_objs
        )
