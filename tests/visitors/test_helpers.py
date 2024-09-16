from unittest.mock import MagicMock, patch

from uc_functions.visitors import is_from_libraries, is_library_module, is_library_path


def test_is_library_module_builtin():
    assert is_library_module("builtins") is True


def test_is_library_module_standard_lib():
    assert is_library_module("os") is True


def test_is_library_module_third_party():
    assert is_library_module("pytest") is True


def test_is_library_module_non_existent():
    assert is_library_module("non_existent_module") is False


def test_is_library_module_local():
    with patch("importlib.import_module") as mock_import_module:
        mock_import_module.return_value = None
        with patch("inspect.getfile") as mock_getfile:
            mock_getfile.return_value = None
            assert is_library_module("local_module") is False


def test_is_library_path_with_lib_indicators():
    assert (
        is_library_path("/usr/local/lib/python3.9/site-packages/some_module.py") is True
    )
    assert is_library_path("/usr/lib/python3.9/lib-dynload/some_module.so") is True


def test_is_library_path_without_lib_indicators():
    assert is_library_path("/home/user/projects/some_module.py") is False
    assert is_library_path("/tmp/some_module.py") is False


def test_is_from_libraries_library():
    mock_globals = {
        "mock_lib": MagicMock(
            __file__="/usr/local/lib/python3.9/site-packages/mock_lib.py"
        )
    }
    with patch(
        "inspect.getfile",
        return_value="/usr/local/lib/python3.9/site-packages/mock_lib.py",
    ):
        assert is_from_libraries("mock_lib", mock_globals) is True


def test_is_from_libraries_non_library():
    mock_globals = {
        "mock_local": MagicMock(__file__="/home/user/projects/mock_local.py")
    }
    with patch("inspect.getfile", return_value="/home/user/projects/mock_local.py"):
        assert is_from_libraries("mock_local", mock_globals) is False


def test_is_from_libraries_invalid_name():
    mock_globals = {"DatabricksSecret": MagicMock()}
    assert is_from_libraries("DatabricksSecret", mock_globals) is True
