from uc_functions import DatabricksSecret


def test_databricks_secret():
    ds = DatabricksSecret(
        scope="my_scope",
        key="my_key",
        default_value="my_default_value",
    )
    assert ds.scope == "my_scope"
    assert ds.key == "my_key"
    assert ds.default_value == "my_default_value"
