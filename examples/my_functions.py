import json

from samples.entrypoint import uc
from uc_functions import DatabricksSecret
from utils.keys import MY_SENSITIVE_KEYS


@uc.register
def redact(maybe_json: str) -> str:
    try:
        value = json.loads(maybe_json)
        for key in MY_SENSITIVE_KEYS:
            if key in value:
                value[key] = "REDACTED"
        return json.dumps(value)
    except json.JSONDecodeError:
        return maybe_json

@uc.register
def redact_w_secret(
    maybe_json: str,
    secret: str = DatabricksSecret(
        scope="my-scope", key="my-key", default_value="default"
    ),
) -> str:
    try:
        value = json.loads(maybe_json)
        for key in MY_SENSITIVE_KEYS:
            if key in value:
                value[key] = "REDACTED"
        print(secret)
        return json.dumps(value)
    except json.JSONDecodeError:
        return maybe_json
