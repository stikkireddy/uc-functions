import pytest

from uc_functions.functions import (
    FunctionArg,
    get_response_sql_type,
    get_sql_type_mapping,
)
from uc_functions.special_kwargs import DatabricksSecret


def test_get_response_sql_type_int():
    def func() -> int:
        return 1

    assert get_response_sql_type(func) == "INTEGER"


def test_get_response_sql_type_float():
    def func() -> float:
        return 1.0

    assert get_response_sql_type(func) == "FLOAT"


def test_get_response_sql_type_string():
    def func() -> str:
        return "test"

    assert get_response_sql_type(func) == "STRING"


def test_get_response_sql_type_boolean():
    def func() -> bool:
        return True

    assert get_response_sql_type(func) == "BOOLEAN"


def test_get_response_sql_type_unsupported():
    class CustomType:
        pass

    def func() -> CustomType:
        return CustomType()

    with pytest.raises(ValueError):
        get_response_sql_type(func)


def test_get_sql_type_mapping_supported_types():
    def func(a: int, b: float, c: str, d: bool):
        pass

    expected = {
        "a": FunctionArg(name="a", type="INTEGER"),
        "b": FunctionArg(name="b", type="FLOAT"),
        "c": FunctionArg(name="c", type="STRING"),
        "d": FunctionArg(name="d", type="BOOLEAN"),
    }
    assert get_sql_type_mapping(func) == expected


def test_get_sql_type_mapping_with_secret():
    def func(
        a: int,
        b: str = DatabricksSecret(scope="scope", key="key", default_value="default"),
    ):
        pass

    secret = DatabricksSecret(scope="scope", key="key", default_value="default")
    # expected = {
    #     'a': FunctionArg(name='a', type='INTEGER'),
    #     'b': FunctionArg(name='b', type='STRING', default=secret)
    # }
    # print(get_sql_type_mapping(func))
    # assert get_sql_type_mapping(func) == expected
    mapping = get_sql_type_mapping(func)
    assert mapping["a"].name == "a", "argument a not found"
    assert mapping["a"].type == "INTEGER", "argument a type is not INTEGER"
    assert mapping["b"].name == "b", "argument b not found"
    assert mapping["b"].type == "STRING", "argument b type is not STRING"
    assert isinstance(
        mapping["b"].default, DatabricksSecret
    ), "argument b default is not secret"
    assert (
        mapping["b"].default.scope == "scope"
    ), "argument b default scope is not correct"
    assert mapping["b"].default.key == "key", "argument b default key is not correct"
    assert (
        mapping["b"].default.default_value == "default"
    ), "argument b default default_value is not correct"


def test_sql_type_error_with_defaults():
    def func(a: int = 1):
        pass

    with pytest.raises(ValueError) as e:
        get_sql_type_mapping(func)
    assert "Default values are not supported for python uc udfs" in str(
        e.value
    ), "Expected error message not found"


def test_get_sql_type_mapping_unsupported_type():
    class CustomType:
        pass

    def func(a: CustomType):
        pass

    with pytest.raises(ValueError):
        get_sql_type_mapping(func)
