from typing import *
import inspect

def store_function_args(func: Callable, **kwargs) -> dict[str, Any]:
    """
    Store function arguments in a dictionary by parameter name.
    Only accepts keyword arguments for clarity and safety.
    
    Args:
        func: The function whose arguments we want to store
        **kwargs: Keyword arguments matching the function parameters
    
    Returns:
        Dict mapping parameter names to their values
        
    Raises:
        TypeError: If required parameters are missing
    """
    sig = inspect.signature(func)

    # This will raise TypeError if required parameters are missing
    bound_args = sig.bind(**kwargs)
    bound_args.apply_defaults()
    return dict(bound_args.arguments)


def call_function_with_named_args(func: Callable, named_args: Dict[str, Any]) -> Any:
    """
    Call a function using stored arguments, respecting positional-only parameters.
    
    Args:
        func: Function to call
        stored_args: Dictionary of arguments keyed by parameter name
    """
    sig = inspect.signature(func)
    pos_args = []
    kw_args = {}
    
    for param_name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            pos_args.append(named_args[param_name])
        else:
            if param_name in named_args:
                kw_args[param_name] = named_args[param_name]
    
    result = func(*pos_args, **kw_args)
    return result


def compile_python_function(code:str)->Callable:
    """takes a python script and return the first function defined in the 
    script. raises Exceptions"""
    import inspect
    capture = {'__builtins__':__builtins__}
    try:
        exec(code, capture)
    except SyntaxError as err:
        raise err
    except Exception as err:
        raise err

    for name, attribute in capture.items():

        if callable(attribute) and not inspect.isclass(attribute) and attribute.__module__ is None:
            return attribute
    raise ValueError("no functions found in script")

import re
def get_function_name(code_string:str)->str:
    match = re.search(r'def\s+(\w+)\s*\(', code_string)
    if not match:
        raise ValueError()
    return match.group(1)

import ast


class UnboundedNameFinder(ast.NodeVisitor):
    def __init__(self):
        self.unbounded_names = list()
        self.defined_names = set()
        self.comprehension_names = set()  # Tracks variables bound in comprehensions

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):  # Variable is being used
            if node.id not in self.defined_names and node.id not in self.comprehension_names:
                if node.id not in self.unbounded_names:
                    self.unbounded_names.append(node.id)
        elif isinstance(node.ctx, ast.Store):  # Variable is being assigned
            self.defined_names.add(node.id)
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Process assigned variables before visiting right-hand side
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined_names.add(target.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Function names should be considered defined
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ListComp(self, node):
        # Handle comprehensions correctly
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self.comprehension_names.add(generator.target.id)
            elif isinstance(generator.target, (ast.Tuple, ast.List)):  # Handles tuple unpacking
                for elt in generator.target.elts:
                    if isinstance(elt, ast.Name):
                        self.comprehension_names.add(elt.id)
        self.generic_visit(node)

    def visit_DictComp(self, node):
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self.comprehension_names.add(generator.target.id)
            elif isinstance(generator.target, (ast.Tuple, ast.List)):  # Handles tuple unpacking
                for elt in generator.target.elts:
                    if isinstance(elt, ast.Name):
                        self.comprehension_names.add(elt.id)
        self.generic_visit(node)

    def visit_SetComp(self, node):
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self.comprehension_names.add(generator.target.id)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                self.comprehension_names.add(generator.target.id)
            elif isinstance(generator.target, (ast.Tuple, ast.List)):  # Handles tuple unpacking
                for elt in generator.target.elts:
                    if isinstance(elt, ast.Name):
                        self.comprehension_names.add(elt.id)
        self.generic_visit(node)

import builtins as _builtins_module


def find_unbounded_names(expr):
    _BUILTIN_NAMES = set(dir(_builtins_module))
    tree = ast.parse(expr, mode='eval')
    finder = UnboundedNameFinder()
    finder.visit(tree)
    return [name for name in finder.unbounded_names if name not in _BUILTIN_NAMES]

import traceback
def format_exception(err:Exception)->str:
    formatted_traceback = ''.join(traceback.TracebackException.from_exception(err).format())
    return formatted_traceback

    # print(f"{e}:")
    # tb = traceback.TracebackException.from_exception(e)
    
    # # Loop through the stack to print the filename, line number, function name, and code
    # for frame in tb.stack:
    #     print(f"  File: {frame.filename}, Line: {frame.lineno}, Function: {frame.name}, Code: {frame.line}")

    # # Alternatively, get just the line number from the last frame (where the exception was raised)
    # last_frame = tb.stack[-1]  # The last frame is where the exception occurred
    # print(f"  Line number of the exception: {last_frame.lineno}")
