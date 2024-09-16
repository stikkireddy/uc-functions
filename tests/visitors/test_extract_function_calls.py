import ast

from uc_functions.visitors import ExtractFunctionCallsVisitor


def test_visit_call_dot_notation():
    code = "submodule.function()"
    tree = ast.parse(code)
    visitor = ExtractFunctionCallsVisitor()
    visitor.visit(tree)
    functions = visitor.get_functions()
    assert len(functions) == 1
    assert functions[0].name == "function"
    assert functions[0].attrs == ["submodule"]


def test_visit_call_dot_notation_os():
    code = "os.path.abs('foobar')"
    tree = ast.parse(code)
    visitor = ExtractFunctionCallsVisitor()
    visitor.visit(tree)
    functions = visitor.get_functions()
    print(functions)
    assert len(functions) == 1
    assert functions[0].module == "os"
    assert functions[0].name == "abs"
    assert functions[0].attrs == ["os", "path"]


def test_visit_call_simple():
    code = "function()"
    tree = ast.parse(code)
    visitor = ExtractFunctionCallsVisitor()
    visitor.visit(tree)
    functions = visitor.get_functions()
    assert len(functions) == 1
    assert functions[0].module == "function"
    assert functions[0].name == "function"
    assert functions[0].attrs == []


def test_visit_call_combined():
    code = """
submodule.function()
another_function()
"""
    tree = ast.parse(code)
    visitor = ExtractFunctionCallsVisitor()
    visitor.visit(tree)
    functions = visitor.get_functions()
    assert len(functions) == 2
    assert functions[0].name == "function"
    assert functions[0].attrs == ["submodule"]
    assert functions[1].module == "another_function"
    assert functions[1].name == "another_function"
    assert functions[1].attrs == []
