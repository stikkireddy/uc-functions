DROP FUNCTION IF EXISTS main.default.redact;

CREATE OR REPLACE FUNCTION main.default.redact(maybe_json STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
import json

MY_SENSITIVE_KEYS = ["email", "phone"]
try:
    value = json.loads(maybe_json)
    for key in MY_SENSITIVE_KEYS:
        if key in value:
            value[key] = "REDACTED"
    return json.dumps(value)
except json.JSONDecodeError:
    return maybe_json

$$;
