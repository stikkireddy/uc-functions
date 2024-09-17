import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from uc_functions.functions import FunctionDeployment

samples_dir = str(Path(__file__).parent.parent / "samples")

if samples_dir not in sys.path:
    sys.path.append(samples_dir)

if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] = f"{os.environ['PYTHONPATH']}:{samples_dir}"
else:
    os.environ["PYTHONPATH"] = samples_dir

CATALOG = "foo"
SCHEMA = "bar"

EXPECTED_REDACT = f"""
DROP FUNCTION IF EXISTS {CATALOG}.{SCHEMA}.redact;

CREATE OR REPLACE FUNCTION foo.bar.redact(maybe_json STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
import json

KEYS_TO_REDACT = ["email", "phone"]
try:
    value = json.loads(maybe_json)
    for key in KEYS_TO_REDACT:
        if key in value:
            value[key] = "REDACTED"
    return json.dumps(value)
except json.JSONDecodeError:
    return maybe_json

$$;
"""


def test_register_no_op_behavior():
    uc = FunctionDeployment("foo", "bar", root_dir=samples_dir)
    from samples.redact import redact

    reg = uc.register(redact)

    data = '{"foo": "bar"}'
    assert reg(data) == data == redact(data), "Function did not return expected value"
    uc.compile()
    # function is only available after compiled
    assert uc.get_function(redact.__name__) is not None, "Function was not registered"

    with open(f"{samples_dir}/compile/{CATALOG}.{SCHEMA}.{redact.__name__}.sql") as f:
        assert (
            f.read().strip() == EXPECTED_REDACT.strip()
        ), "Compiled code is not as expected"


EXPECTED_REDACT_W_SECRET = f"""
DROP FUNCTION IF EXISTS {CATALOG}.{SCHEMA}._redact_w_secret;
DROP FUNCTION IF EXISTS {CATALOG}.{SCHEMA}.redact_w_secret;

CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}._redact_w_secret(maybe_json STRING, secret STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
import json

KEYS_TO_REDACT = ["email", "phone"]
try:
    value = json.loads(maybe_json)
    for key in KEYS_TO_REDACT:
        if key in value:
            value[key] = "REDACTED"
    print(secret)
    return json.dumps(value)
except json.JSONDecodeError:
    return maybe_json

$$;


CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.redact_w_secret(maybe_json STRING)
RETURNS STRING
LANGUAGE SQL 
NOT DETERMINISTIC 
CONTAINS SQL
RETURN SELECT {CATALOG}.{SCHEMA}._redact_w_secret(maybe_json, secret("my-scope", "my-key"));
"""


def test_register_secret_behavior():
    uc = FunctionDeployment("foo", "bar", root_dir=samples_dir)
    from samples.redact_with_secret import redact_w_secret

    reg = uc.register(redact_w_secret)

    data = '{"foo": "bar"}'
    assert (
        reg(data) == data == redact_w_secret(data)
    ), "Function did not return expected value"
    uc.compile(redact_w_secret.__name__)

    with open(
        f"{samples_dir}/compile/{CATALOG}.{SCHEMA}.{redact_w_secret.__name__}.sql"
    ) as f:
        assert (
            f.read().strip() == EXPECTED_REDACT_W_SECRET.strip()
        ), "Compiled code is not as expected"


def test_remote():
    uc = FunctionDeployment(
        "foo",
        "bar",
        root_dir=samples_dir,
    )
    from samples.redact import redact

    reg = uc.register(redact)
    data = '{"foo": "bar"}'

    with patch("uc_functions.functions.run_sql") as mock_run_sql:
        mock_response = MagicMock()
        mock_response.result.as_dict.return_value = {"data_array": [['{"foo": "bar"}']]}
        mock_run_sql.return_value = mock_response

        assert (
            reg.remote(data, workspace_client=MagicMock(), warehouse_id=MagicMock())
            == data
            == redact(data)
        ), "Function did not return expected value"


def test_deploy():
    uc = FunctionDeployment("foo", "bar", root_dir=samples_dir)
    from samples.redact import redact

    uc.register(redact)

    with patch("uc_functions.functions.run_sql") as mock_run_sql:
        uc.deploy(workspace_client=MagicMock(), warehouse_id=MagicMock())
        # assert mock_run_sql called n times
        assert mock_run_sql.call_count == 2, "run_sql was not called"
        mock_run_sql.call_args_list[0].args[2].startswith(
            f"DROP FUNCTION IF EXISTS " f"{CATALOG}.{SCHEMA}.{redact.__name__};"
        )
        mock_run_sql.call_args_list[1].args[2].startswith(
            f"CREATE OR REPLACE FUNCTION "
        )

    with patch("uc_functions.functions.run_sql") as mock_run_sql:
        uc.deploy(
            workspace_client=MagicMock(), warehouse_id=MagicMock(), name=redact.__name__
        )
        # assert mock_run_sql called n times
        assert mock_run_sql.call_count == 2, "run_sql was not called"
        mock_run_sql.call_args_list[0].args[2].startswith(
            f"DROP FUNCTION IF EXISTS " f"{CATALOG}.{SCHEMA}.{redact.__name__};"
        )
        mock_run_sql.call_args_list[1].args[2].startswith(
            f"CREATE OR REPLACE FUNCTION "
        )
