import ast
import builtins
import importlib
import inspect
from dataclasses import dataclass
from typing import Optional


def is_library_module(module_name: str):
    if module_name == "builtins":
        return True
    # 1. Attempt to get the file of the module
    # 2. Handle namespace packages or built-in modules
    # 3. check if module file path is library path
    # 4. if module has no __file__ attribute, most likely it's a built-in module
    try:
        module = importlib.import_module(module_name)
        try:
            # Attempt to get the file of the module
            module_file = inspect.getfile(module)
            if module_file is None:
                print(f"{module_name} is probably local code.")
                return False
            return is_library_path(module_file)
        except TypeError:
            if hasattr(module, "__file__"):
                return is_library_path(module.__file__)
            else:
                print(f"{module_name} is a built-in module or a namespace package.")
                return False
    except (ImportError, TypeError):
        return False


def is_library_path(path):
    # Check if the path contains any of the following strings to determine if it's a library path
    probably_libs = ["site-packages", "lib-dynload", "dist-packages", "lib/python"]
    for lib in probably_libs:
        if lib in path:
            return True
    return False


@dataclass
class ImportObj:
    module_path: Optional[str]
    obj_name: str
    alias: Optional[str]

    def to_importlib_obj(self):
        if self.module_path is None:
            return importlib.import_module(self.obj_name)
        return getattr(importlib.import_module(self.module_path), self.obj_name)


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.import_objs = []

    def visit_Import(self, node):
        for alias in node.names:
            if is_library_module(alias.name) is False:
                continue
            if alias.asname is None:
                self.imports.add(f"import {alias.name}")
                self.import_objs.append(ImportObj(None, alias.name, None))
            else:
                self.import_objs.append(ImportObj(None, alias.name, alias.asname))
                self.imports.add(f"import {alias.name} as {alias.asname}")

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.asname is None:
                self.import_objs.append(ImportObj(node.module, alias.name, None))
            else:
                self.import_objs.append(
                    ImportObj(node.module, alias.name, alias.asname)
                )
        if node.module is not None and is_library_module(node.module) is True:
            self.imports.add(
                f"from {node.module} import {', '.join([alias.name for alias in node.names])}"
            )


class ASTNameNodeMappingExtractor(ast.NodeVisitor):
    def __init__(self):
        self.name_dict = {}

    def visit_FunctionDef(self, node):
        self.name_dict[node.name] = node
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.name_dict[node.name] = node
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Check if it's a single assignment to a variable
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self.name_dict[node.targets[0].id] = node
        self.generic_visit(node)


def is_from_libraries(name, globals_dict):
    probably_libs = ["site-packages", "lib-dynload", "dist-packages", "lib/python"]
    potential_paths = []
    if hasattr(globals_dict[name], "__file__") is True:
        potential_paths.append(globals_dict[name].__file__)
    invalid_names = ["DatabricksSecret"]
    if name in invalid_names:
        print(f"{name} is a built in library class that should be ignored")
        return True
    potential_paths.append(inspect.getfile(globals_dict[name]))
    for path in potential_paths:
        for lib in probably_libs:
            if lib in path:
                print(f"{name} is probably a library")
                return True
    return False


class ReplaceDotsTransformer(ast.NodeTransformer):

    # TODO: probably should remove since its not too relevant

    def __init__(self, globals_dict):
        self.globals_dict = globals_dict

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if (
                name in self.globals_dict
                and is_from_libraries(name, self.globals_dict) is False
            ):
                return ast.Call(
                    func=ast.Name(id=name, ctx=ast.Load()),
                    args=node.args,
                    keywords=node.keywords,
                )
        return node


class ImportOptimizer(ast.NodeTransformer):
    def __init__(self):
        self.used_names = set()
        self.imported_names = {}
        self.seen_imports = set()

    def visit_Import(self, node):
        key = tuple(sorted(alias.asname or alias.name for alias in node.names))
        if key in self.seen_imports:
            return None  # Remove duplicate
        self.seen_imports.add(key)
        for alias in node.names:
            self.imported_names[alias.asname or alias.name] = node
        return node

    def visit_ImportFrom(self, node):
        key = (node.module, tuple(sorted(alias.name for alias in node.names)))
        if key in self.seen_imports:
            return None  # Remove duplicate
        self.seen_imports.add(key)
        for alias in node.names:
            self.imported_names[alias.asname or alias.name] = node
        return node

    def visit_Name(self, node):
        self.used_names.add(node.id)
        return node

    def optimize_imports(self, tree):
        self.visit(tree)
        for name in list(self.imported_names):
            if name not in self.used_names:
                try:
                    tree.body.remove(self.imported_names[name])
                except ValueError as e:
                    print(f"Error removing import {name}: {e}; most likely removed")
                    pass


@dataclass
class FunctionMetadata:
    module: str  # globals search name may just be function directly
    name: str
    attrs: list[str]  # things like os.path.abs ("os", "path") will show up in attrs

    def unique_name(self):
        return "_".join(self.attrs)

    def get_module_obj(self, globals_dict):
        if self.module is None:
            return None
        if self.module in globals_dict:
            return globals_dict[self.module]
        return importlib.import_module(self.module)

    def is_builtin_library(self, globals_dict):
        if self.module is None:
            return None
        try:
            mod = self.get_module_obj(globals_dict)
            if hasattr(mod, "__file__"):
                return is_library_path(mod.__file__)
            else:
                return is_library_path(inspect.getfile(mod))
        except Exception as e:
            print(f"Error checking if {self.module} is a library: {e}")
            return False


class ExtractFunctionCallsVisitor(ast.NodeVisitor):

    def __init__(self):
        self._function_metadata_list = []
        self._visited_functions = set()

    def get_functions(self) -> list[FunctionMetadata]:
        return self._function_metadata_list

    @staticmethod
    def _handle_attr_based_function_call(node: ast.Attribute):
        attributes = []
        current_node = node.func
        top_level_name = None

        while isinstance(current_node, ast.Attribute):
            attributes.append(current_node.attr)
            current_node = current_node.value
        # Check if the top-level node is an ast.Name, indicating a module or variable
        # then extract the module or variable name
        if isinstance(current_node, ast.Name):
            attributes.append(current_node.id)
            attributes.reverse()
            top_level_name = current_node.id
        return FunctionMetadata(
            module=top_level_name, name=attributes[-1], attrs=attributes[:-1]
        )

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            metadata = self._handle_attr_based_function_call(node)
            if metadata.unique_name() not in self._visited_functions:
                self._visited_functions.add(metadata.unique_name())
                self._function_metadata_list.append(metadata)
        elif isinstance(node.func, ast.Name):
            if node.func.id not in self._visited_functions:
                self._visited_functions.add(node.func.id)
                self._function_metadata_list.append(
                    FunctionMetadata(module=node.func.id, name=node.func.id, attrs=[])
                )
        self.generic_visit(node)


class UnresolvedNamesFinder(ast.NodeVisitor):
    def __init__(self, defined_names: list[str] = None):
        self.defined_names = set(defined_names or [])
        self.used_names = set()

    def visit_Import(self, node):
        for alias in node.names:
            if alias.asname:
                self.defined_names.add(alias.asname)
            self.defined_names.add(alias.name)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.asname:
                self.defined_names.add(alias.asname)
            self.defined_names.add(alias.asname if alias.asname else alias.name)

    def visit_FunctionDef(self, node):
        self.defined_names.add(node.name)
        # add the function args to defined names
        if hasattr(node, "args") and hasattr(node.args, "args"):
            for arg in node.args.args:
                if hasattr(arg, "arg") and arg.arg is not None:
                    self.defined_names.add(arg.arg)
        # todo add args as defined names
        # print([arg.arg for arg in node.args.args])
        # self.defined_names.add(node.args)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined_names.add(target.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id not in dir(builtins):
            self.used_names.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            self.defined_names.add(node.id)
        self.generic_visit(node)

    def get_undefined_names(self):
        return self.used_names - self.defined_names
