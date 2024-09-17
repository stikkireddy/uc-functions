# uc-functions

![GitHub License](https://img.shields.io/github/license/stikkireddy/uc-functions)
![Build](https://github.com/stikkireddy/uc-functions/actions/workflows/build.yaml/badge.svg)
[![codecov](https://codecov.io/github/stikkireddy/uc-functions/branch/main/graph/badge.svg?token=EORUY66PNQ)](https://codecov.io/github/stikkireddy/uc-functions)
![GitHub Tag](https://img.shields.io/github/v/tag/stikkireddy/uc-functions)

The purpose of this project is to help you manage unity catalog python functions as traditional python code and be
able to easily unit test, integration test and deploy them to Databricks. As part of a compilation step this package
converts python AST to unity catalog functions. It also handles things like secrets, etc. by adding a layer of
indirection using SQL based UDFs.

Other solutions may attempt to use packages like pickle or cloudpickle to serialize the functions. This is not recommended in 
practice as it can lead to environment discrepancies. Cloudpickle works best if you are using the same python version and 
same version of cloudpickle. This is hard to at the moment with serverless environments. This is also not readable and 
you will see a giant base64 encoded string in your code. `uc-functions` goal is to properly transpile the python code to 
sql code and handle the majority of the edge cases by inlining all references in the function.

> Using cloudpickle for long-term object storage is not supported and strongly discouraged.
> 
> Reference: https://github.com/cloudpipe/cloudpickle

## Installation

```bash
pip install uc-functions
```

## Goals

Convert decorated python functions to sql functions that can be deployed to Databricks. This is useful for managing
large number of functions with reusable code. Easy way to test and debug functions.

In this following example code, this project will convert the python function to a SQL function. It also scans for all
unidentified names, functions, etc. and tries to inline them as much as possible in the SQL functions.

```python
import json
from pathlib import Path
from utils.keys import MY_SENSITIVE_KEYS

from uc_functions import FunctionDeployment

root_dir = str(Path(__file__).parent)
uc = FunctionDeployment("main",
                        "default",
                        root_dir,
                        globals_dict=globals())


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
```

Will get converted to:

```sql
DROP FUNCTION IF EXISTS main.default.redact;

CREATE
OR
REPLACE
FUNCTION main.default.redact(maybe_json STRING)
RETURNS STRING
LANGUAGE PYTHON
AS $$
import
json

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
```

## Features

* Convert python functions to SQL functions
* Handle secrets
* Inline function references
* Handle imports
* Debug unidentified names
* Easy unit testing and integration testing
* Dynamic sys.path using python files in volumes (soon TBD) 

## Unit testing

`@uc.register` is a decorator that only modifies attributes of the function. It does not modify the function 
inputs and outputs themselves. This makes it easy to unit test the functions.

Example function

```python
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
```

Example unit test

```python
def test_redact():
    assert redact('{"email": "foo", "phone": "bar"}') == '{"email": "REDACTED", "phone": "REDACTED"}'
```

## Integration testing

Integration testing is done by deploying the functions and it will test using the remote attribute added to the function.

Register Function:

```python
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
```

Once deployed run this:

```python
# executes the code on a remote databricks warehouse
redact.remote(
    '{"email": "foo", "phone": "bar"}',
    # workspace_client=workspace_client, # make sure you pass the workspace client or provide environment variables
    # warehouse_id=warehouse_id # optional otherwise it will pick first serverless warehouse
)
```

## Usage

Look in examples on how to use and what the compiled output looks like in the `examples` directory.

* Example code: [examples/my_functions.py](examples/my_functions.py)
* Compile Script: [examples/compile.py](examples/compile.py)
* Compiled SQL Stmts: [examples/compile](examples/compile)
* Deploy script: [examples/deploy.py](examples/deploy.py)

## Disclaimer

uc-functions package is not developed, endorsed not supported by Databricks. It is provided as-is; no warranty is
derived from using this package. For more details, please refer to the license.
