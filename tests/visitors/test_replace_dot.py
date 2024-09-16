import ast
from unittest.mock import MagicMock, patch

from uc_functions.visitors import ReplaceDotsTransformer


def test_replace_dots_transformer():
    # The goal of this is to remove all dots since we will be inlining all functions
    code = """
mock_lib.some_function()
mock_lib.another_function()
"""
    tree = ast.parse(code)
    mock_globals = {
        "some_function": MagicMock(),
        "another_function": MagicMock(),
        "mock_lib": MagicMock(),
    }

    with patch("uc_functions.visitors.is_from_libraries", return_value=False):
        transformer = ReplaceDotsTransformer(mock_globals)
        transformed_tree = transformer.visit(tree)
        transformed_code = ast.unparse(transformed_tree)

    expected_code = """
some_function()
another_function()
"""
    assert transformed_code.strip() == expected_code.strip()
