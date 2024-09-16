DROP FUNCTION IF EXISTS main.default._redact_w_secret;
DROP FUNCTION IF EXISTS main.default.redact_w_secret;

CREATE OR REPLACE FUNCTION main.default._redact_w_secret(maybe_json STRING, secret STRING)
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
    print(secret)
    return json.dumps(value)
except json.JSONDecodeError:
    return maybe_json

$$;


CREATE OR REPLACE FUNCTION main.default.redact_w_secret(maybe_json STRING)
RETURNS STRING
LANGUAGE SQL 
NOT DETERMINISTIC 
CONTAINS SQL
RETURN SELECT main.default._redact_w_secret(maybe_json, secret("my-scope", "my-key"));
