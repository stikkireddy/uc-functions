import os
import sys
from pathlib import Path

import pytest

from uc_functions.inline import inline_function

samples_dir = str(Path(__file__).parent.parent / "samples")

if samples_dir not in sys.path:
    sys.path.append(samples_dir)

if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] = f"{os.environ['PYTHONPATH']}:{samples_dir}"
else:
    os.environ["PYTHONPATH"] = samples_dir


expected_result = """
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
"""


def test_inline():
    from samples.redact import redact

    inline_function(redact, samples_dir)
    assert redact._inlined == True, "Function was not inlined"
    assert (
        redact._inlined_code.strip() == expected_result.strip()
    ), "Inlined code is not as expected"


def test_undefined_names():
    from samples.redact_with_undefined_name import redact_undefined

    with pytest.raises(ValueError) as e:
        inline_function(redact_undefined, samples_dir)
    assert "Unable to resolve the following names" in str(
        e.value
    ), "Expected error message not found"
    assert "foobar" in str(e.value), "Expected error message not found"


def test_lint_code_for_undefined_names():
    from uc_functions.inline import RecursiveResolver

    r = RecursiveResolver()
    code = """
print(foobar)
"""
    undefined_names = r.lint_code_for_undefined_names(code)
    assert len(undefined_names) == 1, "Expected 1 undefined name"
    assert "foobar" in undefined_names[0], "Expected undefined name not found"
