import json

from shared_utils.shared_keys import KEYS_TO_REDACT

from uc_functions import DatabricksSecret


def redact_w_secret(
    maybe_json: str,
    secret: str = DatabricksSecret(
        scope="my-scope", key="my-key", default_value="default"
    ),
) -> str:
    try:
        value = json.loads(maybe_json)
        for key in KEYS_TO_REDACT:
            if key in value:
                value[key] = "REDACTED"
        print(secret)
        return json.dumps(value)
    except json.JSONDecodeError:
        return maybe_json
