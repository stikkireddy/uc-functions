import ast
import functools
import inspect
import os
import types
from io import StringIO
from typing import Callable

import astor
import black

from uc_functions.special_kwargs import DatabricksSecret
from uc_functions.visitors import (
    ASTNameNodeMappingExtractor,
    ExtractFunctionCallsVisitor,
    ImportOptimizer,
    ImportVisitor,
    ReplaceDotsTransformer,
    UnresolvedNamesFinder,
)


def get_obj_source(obj):
    try:
        return inspect.getsource(obj)
    except Exception as e:
        print(f"Error getting source for {obj}: {e}")
        return None


def get_obj_file_source(obj):
    file = inspect.getfile(obj)
    with open(file, "r") as f:
        return f.read()


def find_undefined_names(source_code, skip_these_names: list[str] = None):
    tree = ast.parse(source_code)
    finder = UnresolvedNamesFinder(skip_these_names)
    finder.visit(tree)
    return finder.get_undefined_names()


# Not being used kept for reference
# def get_imported_module_with_file(module_name, globals_dict, current_file=None, visited=None):
#     if visited is None:
#         visited = set()
#
#     if module_name in globals_dict and isinstance(globals_dict[module_name], types.ModuleType):
#         return globals_dict[module_name], current_file
#
#     for obj in globals_dict.values():
#         if isinstance(obj, types.ModuleType) and obj not in visited:
#             visited.add(obj)
#             imported_module_globals = vars(obj)
#             if module_name in imported_module_globals and isinstance(imported_module_globals[module_name],
#                                                                      types.ModuleType):
#                 module_file = getattr(obj, '__file__', 'Unknown file')
#                 return imported_module_globals[module_name], module_file
#
#             result, file = get_imported_module_with_file(module_name, imported_module_globals,
#                                                          getattr(obj, '__file__', current_file), visited)
#             if result is not None:
#                 return result, file
#     return None, None


@functools.lru_cache(maxsize=32)
def generate_ast_dict(directory):
    print(f"Generating AST dictionary for {directory}")
    name_dict = {}

    # TODO: support gitignore refspec
    key_segments_to_skip = [r"/site-packages/", r"/.venv/", r"/venv/", r"/virtualenv/"]

    for root, _, files in os.walk(directory):
        for filename in files:
            if any([segment in root for segment in key_segments_to_skip]):
                continue
            if filename.endswith(".py"):
                file_path = os.path.join(root, filename)
                print("Indexing: ", file_path)
                with open(file_path, "r", encoding="utf-8") as file:
                    source_code = file.read()
                    node = ast.parse(source_code, filename=file_path)
                    extractor = ASTNameNodeMappingExtractor()
                    extractor.visit(node)
                    name_dict.update(extractor.name_dict)

    return name_dict


class RecursiveResolver:

    def __init__(
        self, skip_classes=None, name_ast_dict=None, args_names_predefined=None
    ):
        self.name_ast_dict = name_ast_dict
        self.root_function_code = None
        self.functions_code = []
        self.already_visited_functions = set()
        self.imports = set()
        self.skip_classes = skip_classes or []
        self.arg_names_predefined = args_names_predefined or []

    def get_imports_from_func_file(self, obj):
        file = get_obj_file_source(obj)
        tree = ast.parse(file)
        visitor = ImportVisitor()
        visitor.visit(tree)
        return visitor.imports

    def resolve(self, obj, globals_dict, is_root_function: bool = False):
        src = get_obj_source(obj)
        if src is None:
            return
        if obj in self.skip_classes:
            return
        if isinstance(obj, types.ModuleType):
            # skip modules we only want code for functions and classes
            return
        for import_stmt in self.get_imports_from_func_file(obj):
            self.imports.add(import_stmt)
        if is_root_function:
            self.root_function_code = src
        else:
            self.functions_code.append(src)
        tree = ast.parse(src)
        visitor = ExtractFunctionCallsVisitor()
        visitor.visit(tree)
        for function_metadata in visitor.get_functions():
            if function_metadata.module is None:
                continue
            if function_metadata.is_builtin_library(globals_dict):
                continue
            function_obj = globals_dict.get(function_metadata.module)
            if len(function_metadata.attrs) > 1:
                for attr in function_metadata.attrs[1:]:
                    function_obj = getattr(function_obj, attr)
            self.resolve(function_obj, globals_dict)

    @staticmethod
    def stitch_code(imports, deps, root) -> ast.Module:
        new_body = []
        new_body.extend(imports)
        new_body.extend(deps)
        new_body.extend(root)
        return ast.Module(body=new_body)

    @staticmethod
    def format(code: str):
        return black.format_str(code, mode=black.FileMode(line_length=80))

    @staticmethod
    def lint_code_for_undefined_names(code: str):
        import pyflakes.api
        import pyflakes.reporter

        output = StringIO()
        reporter = pyflakes.reporter.Reporter(output, output)

        pyflakes.api.check(code, "source_code.py", reporter)

        output_value = output.getvalue()
        output.close()

        undefined_names = []
        for line in output_value.splitlines():
            if "undefined name" in line:
                undefined_names.append(line)

        return undefined_names

    def get_inline(self, globals_dict, recursion_limit=100):
        root = ast.parse(self.root_function_code)
        retries = 1
        prev_undefined_names = set()
        final_code = None
        # Naively recurse until all undefined names are resolved
        # This is a brute force approach and may not be the most efficient
        # but it should work for most cases and is simplest to debug.
        # It will repetitively try to resolve undefined names through various
        # means. If previous undefined names are the same as current undefined
        # that means there is a field that is unable to be resolved.
        while retries <= recursion_limit:
            print(f"Attempting to inline {retries} times")
            imports_code = "\n".join(self.imports)
            imports_tree = ast.parse(imports_code)
            dep_code = "\n\n".join(reversed(self.functions_code))
            dep_tree = ast.parse(dep_code)
            new_tree = self.stitch_code(
                imports_tree.body, dep_tree.body, root.body[0].body
            )
            replace_dot_call = ReplaceDotsTransformer(globals_dict)
            new_tree = replace_dot_call.visit(new_tree)
            io = ImportOptimizer()
            io.optimize_imports(new_tree)
            final_code = astor.to_source(new_tree)
            final_code = self.format(final_code)
            undefined_names = find_undefined_names(
                final_code, skip_these_names=self.arg_names_predefined
            )
            if len(undefined_names) == 0:
                return final_code
            for name in undefined_names:
                if name in self.name_ast_dict:
                    self.functions_code.append(
                        astor.to_source(self.name_ast_dict[name])
                    )
            if prev_undefined_names == undefined_names:
                raise ValueError(
                    "Unable to resolve the following names:", undefined_names
                )
            prev_undefined_names = undefined_names
            retries += 1

        final_undefined_names = self.lint_code_for_undefined_names(final_code)
        if len(final_undefined_names) == 0:
            return final_code
        raise ValueError(
            "Unable to resolve the following names in your code:", final_undefined_names
        )


# Commented for future reference not referred anywhere
# def load_functions_and_classes_from_directory(directory: str):
#     func_class_dict = {}
#
#     for root, _, files in os.walk(directory):
#         for filename in files:
#             if filename.endswith('.py') and not filename.startswith('__init__.py'):
#                 file_path = os.path.join(root, filename)
#                 module_name = os.path.splitext(os.path.relpath(file_path, directory))[0].replace(
#                     os.sep, '.')
#
#                 try:
#
#                     spec = importlib.util.spec_from_file_location(module_name, file_path)
#                     module = importlib.util.module_from_spec(spec)
#
#                     for name, obj in module.__dict__.items():
#                         func_class_dict[name] = obj
#                 except Exception as e:
#                     pass
#
#     return func_class_dict


def inline_function(function: Callable, code_root: str, globals_dict=None):
    arg_spec = inspect.getfullargspec(function)
    arg_names = arg_spec.args + arg_spec.kwonlyargs
    name_to_ast_node = generate_ast_dict(code_root)
    r = RecursiveResolver(
        skip_classes=[DatabricksSecret],
        name_ast_dict=name_to_ast_node,
        args_names_predefined=arg_names,
    )
    # TODO: explore doing this without a recursion error when executing the module
    # for super edge cases like importlib, etc.
    # should not need to load modules, should be able to do this entirely via ast.
    # only hard things to do with ast is things like importlib, etc. which then you need to exec the module
    # functions_dict = load_functions_and_classes_from_directory(code_root)
    # _globals_dict = {**functions_dict, **(globals_dict or globals())}
    # print(_globals_dict)
    _globals_dict = {**(globals_dict or globals())}
    r.resolve(function, _globals_dict, is_root_function=True)
    code = r.get_inline(_globals_dict)
    function._inlined = True
    function._inlined_code = code
    return function
