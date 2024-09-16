import ast

from uc_functions.visitors import ASTNameNodeMappingExtractor


def test_visit_function_def_single():
    code = "def foo(): pass"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "foo" in extractor.name_dict


def test_visit_function_def_multiple():
    code = "def foo(): pass\ndef bar(): pass"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "foo" in extractor.name_dict
    assert "bar" in extractor.name_dict


def test_visit_class_def_single():
    code = "class Foo: pass"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "Foo" in extractor.name_dict


def test_visit_class_def_multiple():
    code = "class Foo: pass\nclass Bar: pass"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "Foo" in extractor.name_dict
    assert "Bar" in extractor.name_dict


def test_visit_assign_single():
    code = "x = 1"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "x" in extractor.name_dict


def test_visit_assign_multiple():
    code = "x = 1\ny = 2"
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "x" in extractor.name_dict
    assert "y" in extractor.name_dict


def test_combined_definitions():
    code = """
def foo(): pass
class Bar: pass
x = 1
"""
    tree = ast.parse(code)
    extractor = ASTNameNodeMappingExtractor()
    extractor.visit(tree)
    assert "foo" in extractor.name_dict
    assert "Bar" in extractor.name_dict
    assert "x" in extractor.name_dict
