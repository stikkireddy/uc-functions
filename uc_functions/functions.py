import functools
import inspect
import os.path
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from uc_functions.inline import inline_function
from uc_functions.special_kwargs import DatabricksSecret

python_to_sql_type_mapping = {
    int: "INTEGER",
    float: "FLOAT",
    str: "STRING",
    bool: "BOOLEAN",
}


def get_response_sql_type(func: Callable) -> str:
    signature = inspect.signature(func)
    return_type = signature.return_annotation
    sql_type = python_to_sql_type_mapping.get(return_type, "UNKNOWN")
    if sql_type == "UNKNOWN":
        raise ValueError(
            f"Unknown SQL type for Python return type: {return_type}, "
            f"only the following types are supported: {python_to_sql_type_mapping}"
        )
    return sql_type


@dataclass
class FunctionArg:
    name: str
    type: str
    default: Any = None

    def to_arg_string(self):
        return f"{self.name} {self.type}"

    def to_call_string(self):
        return self.name

    def to_secret_call_string(self):
        if isinstance(self.default, DatabricksSecret):
            return f'secret("{self.default.scope}", "{self.default.key}")'


def get_sql_type_mapping(func: Callable) -> Dict[str, FunctionArg]:
    signature = inspect.signature(func)
    sql_type_mapping = {}

    for name, param in signature.parameters.items():
        param_type = param.annotation
        sql_type = python_to_sql_type_mapping.get(param_type, "UNKNOWN")
        if sql_type == "UNKNOWN":
            raise ValueError(
                f"Unknown SQL type for Python type: {param_type}, "
                f"only the following types are supported: {python_to_sql_type_mapping}"
            )
        default_param = (
            param.default if param.default != inspect.Parameter.empty else None
        )
        if (
            default_param is not None
            and isinstance(default_param, DatabricksSecret) is False
        ):
            raise ValueError("Default values are not supported for python uc udfs")

        sql_type_mapping[name] = FunctionArg(
            name=name, type=sql_type, default=default_param
        )

    return sql_type_mapping


@dataclass
class FunctionSerialized:
    args: dict[str, FunctionArg]
    response_type: str
    function_b64: str = None
    function_inlined: str = None
    function_name: str = None
    catalog: str = None
    schema: str = None

    def contains_secrets(self):
        return any(
            isinstance(arg.default, DatabricksSecret) for arg in self.args.values()
        )

    def generate_drop_statements(self):
        if self.contains_secrets():
            yield f"DROP FUNCTION IF EXISTS {self.catalog}.{self.schema}._{self.function_name};"
        yield f"DROP FUNCTION IF EXISTS {self.catalog}.{self.schema}.{self.function_name};"

    def generate_create_statements(self):
        args = ", ".join([v.to_arg_string() for v in self.args.values()])
        args_for_invoke = ", ".join([k for k in self.args.keys()])
        if self.contains_secrets():
            f_name = (
                "_" + self.function_name
            )  # make private and have a higher level calling
            # function to obfuscate the secrets away
        else:
            f_name = self.function_name

        if self.function_b64 is not None:
            # TODO: remove cloud pickle option
            yield textwrap.dedent(
                f"""
CREATE OR REPLACE FUNCTION {self.catalog}.{self.schema}.{f_name}({args})
RETURNS {self.response_type}
LANGUAGE PYTHON
AS $$
import base64
import cloudpickle
func = cloudpickle.loads(base64.b64decode('{self.function_b64}'.encode('utf-8')))
return func({args_for_invoke})
$$;
                    """
            )
        if self.function_inlined is not None:
            yield textwrap.dedent(
                f"""
CREATE OR REPLACE FUNCTION {self.catalog}.{self.schema}.{f_name}({args})
RETURNS {self.response_type}
LANGUAGE PYTHON
AS $$
{self.function_inlined}
$$;
"""
            )

        if self.contains_secrets() is True:
            args = ", ".join(
                [v.to_arg_string() for v in self.args.values() if v.default is None]
            )
            calls = ", ".join(
                [
                    (
                        v.to_call_string()
                        if isinstance(v.default, DatabricksSecret) is False
                        else v.to_secret_call_string()
                    )
                    for v in self.args.values()
                ]
            )
            f_name = self.function_name

            yield textwrap.dedent(
                f"""
CREATE OR REPLACE FUNCTION {self.catalog}.{self.schema}.{f_name}({args})
RETURNS {self.response_type}
LANGUAGE SQL 
NOT DETERMINISTIC 
CONTAINS SQL
RETURN SELECT {self.catalog}.{self.schema}._{f_name}({calls});
"""
            )


def run_sql(
    ws_client: WorkspaceClient, warehouse_id: str, stmt: str, wait_timeout="10s"
):
    print("Executing statement: ", stmt)
    resp = ws_client.statement_execution.execute_statement(
        stmt, warehouse_id=warehouse_id, wait_timeout=wait_timeout
    )
    while resp.status.state not in [
        StatementState.CANCELED,
        StatementState.FAILED,
        StatementState.CLOSED,
        StatementState.SUCCEEDED,
    ]:
        resp = ws_client.statement_execution.get_statement(resp.statement_id)
        time.sleep(1)

    if resp.status.state.value != "SUCCEEDED":
        print("Statement failed to execute. Statement: ", stmt)
        print("Result was: ", resp)
        raise ValueError("Statement failed to execute", resp)
    return resp


class FunctionDeployment:

    def __init__(
        self,
        catalog: str,
        schema: str,
        root_dir: str,
        compile_sql_dir: str = "./compile",
        globals_dict=None,
    ):
        self.compile_sql_dir = compile_sql_dir
        self.root_dir = root_dir
        self.catalog = catalog
        self.schema = schema
        self.globals_dict = globals_dict or {}
        self._raw_functions: dict[str, Callable] = {}
        self._serialized_functions: dict[str, FunctionSerialized] = {}

    def _add_function_remote_args(self, function: Callable, orig: Callable):
        function.remote_args = get_sql_type_mapping(orig)

    def _add_function_remote_name(self, function: Callable, function_name: str):
        function.remote_name = f"{self.catalog}.{self.schema}.{function_name}"

    def _add_function_remote_call(self, function: Callable, function_name: str):
        def remote(*args, _wait_timeout="10s", **kwargs):
            provided_ws_client: Optional[WorkspaceClient] = kwargs.pop(
                "workspace_client", None
            )
            provided_warehouse_id: Optional[str] = kwargs.pop("warehouse_id", None)
            if kwargs:
                raise ValueError("Keyword arguments are not supported in remote calls")
            assert (
                provided_ws_client is not None
            ), "Workspace client must be provided, foo.remote(workspace_client=...)"
            assert (
                provided_warehouse_id is not None
            ), "Warehouse id must be provided, foo.remote(warehouse_id)=...)"
            # wrap string args in quotes
            args = [f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in args]
            resp = run_sql(
                provided_ws_client,
                provided_warehouse_id,
                f"SELECT {self.catalog}.{self.schema}.{function_name}({', '.join(args)})",
                wait_timeout=_wait_timeout,
            )
            # resp
            data = resp.result.as_dict().get("data_array", [])
            if len(data) == 0:
                raise ValueError("No data returned from function: " + str(data))
            if len(data[0]) == 0:
                raise ValueError("No data returned from function")
            return data[0][0]

        function.remote = remote

    def _add_function(self, function: Callable):
        assert hasattr(function, "_inlined"), "Function must be inlined"
        assert hasattr(function, "_inlined_code"), "Function must be inlined"
        self._serialized_functions[function.__name__] = FunctionSerialized(
            function_inlined=getattr(function, "_inlined_code"),
            args=get_sql_type_mapping(function),
            response_type=get_response_sql_type(function),
            function_name=function.__name__,
            catalog=self.catalog,
            schema=self.schema,
        )
        # For future reference: we do not want to cloudpickle as it is not good for long term storage.
        # if not hasattr(function, "_inlined"):
        #     import cloudpickle
        #     pickled_func = cloudpickle.dumps(function, protocol=0)
        #     b64 = base64.b64encode(pickled_func).decode("utf-8")
        #     self._serialized_functions[function.__name__] = FunctionSerialized(
        #         function_b64=b64,
        #         args=get_sql_type_mapping(function),
        #         response_type=get_response_sql_type(function),
        #         function_name=function.__name__,
        #         catalog=self.catalog,
        #         schema=self.schema
        #     )
        # else:
        #     self._serialized_functions[function.__name__] = FunctionSerialized(
        #         function_inlined=getattr(function, "_inlined_code"),
        #         args=get_sql_type_mapping(function),
        #         response_type=get_response_sql_type(function),
        #         function_name=function.__name__,
        #         catalog=self.catalog,
        #         schema=self.schema
        #     )

    def generate_deployment_sql(self, name) -> Iterator[str]:
        function: FunctionSerialized = self._serialized_functions[name]
        yield from function.generate_drop_statements()
        yield from function.generate_create_statements()

    def ensure_and_get_compile_path(self, name) -> Path:
        if os.path.isabs(self.compile_sql_dir) is False:
            compile_dir = Path(os.path.join(self.root_dir, self.compile_sql_dir))
        else:
            compile_dir = Path(self.compile_sql_dir)
        compile_dir.mkdir(exist_ok=True)
        function: FunctionSerialized = self._serialized_functions[name]
        # TODO: probably should refactor this into the class
        return compile_dir / f"{function.catalog}.{function.schema}.{name}.sql"

    def _deploy_by_name(
        self, name, workspace_client: WorkspaceClient, warehouse_id: str
    ):
        print(f"Deploying function: {name}")
        stmts = self._compile_by_name(name)
        for stmt in stmts:
            run_sql(workspace_client, warehouse_id, stmt)

    @staticmethod
    def _get_first_warehouse_id(ws_client: WorkspaceClient):
        for warehouse in ws_client.warehouses.list():
            if warehouse.enable_serverless_compute is False:
                continue
            return warehouse.id

    # require kwargs
    def deploy(
        self,
        *,
        workspace_client: WorkspaceClient = None,
        warehouse_id: str = None,
        name=None,
    ):
        if workspace_client is None:
            workspace_client = WorkspaceClient()
        if warehouse_id is None:
            warehouse_id = self._get_first_warehouse_id(workspace_client)

        if name:
            self._deploy_by_name(name, workspace_client, warehouse_id)
            return
        for name in self._raw_functions.keys():
            self._deploy_by_name(name, workspace_client, warehouse_id)

    def _compile_by_name(self, name):
        # should serialize function if it has not already been done
        print(f"Compiling: {name}")
        self.serialize_fn(name)
        stmts_generated = []
        for stmt in self.generate_deployment_sql(name):
            stmts_generated.append(stmt)
        self.ensure_and_get_compile_path(name).write_text("\n".join(stmts_generated))
        return stmts_generated

    def compile(self, name=None):
        if name:
            self._compile_by_name(name)
            return
        for name in self._raw_functions.keys():
            self._compile_by_name(name)

    def get_function(self, name: str) -> FunctionSerialized:
        return self._serialized_functions[name]

    def serialize_fn(self, name):
        if name not in self._serialized_functions:
            function = self._raw_functions[name]
            inlined_func = inline_function(
                function, self.root_dir, globals_dict={**globals(), **self.globals_dict}
            )
            self._add_function(inlined_func)

    def register(self, function: Callable):
        self._raw_functions[function.__name__] = function
        f_args = get_sql_type_mapping(function)

        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            fixed_kwargs = {
                k: v.default.default_value
                for k, v in f_args.items()
                if isinstance(v.default, DatabricksSecret)
            }
            return function(*args, **{**kwargs, **fixed_kwargs})

        self._add_function_remote_args(wrapper, function)
        self._add_function_remote_name(wrapper, function.__name__)
        self._add_function_remote_call(wrapper, function.__name__)
        return wrapper
