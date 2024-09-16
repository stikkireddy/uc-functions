import json

from shared_utils.shared_keys import KEYS_TO_REDACT


def redact(maybe_json: str) -> str:
    try:
        value = json.loads(maybe_json)
        for key in KEYS_TO_REDACT:
            if key in value:
                value[key] = "REDACTED"
        return json.dumps(value)
    except json.JSONDecodeError:
        return maybe_json
