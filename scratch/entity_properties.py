import ast

class EntityProperty:
    def __init__(self, *args):
        self._args = args

def make_entity_property_class(name, prop_args):
    """
    name: string
    prop_args: list of (arg name, arg datatype) tuples
    """
    constructor_body = []
    constructor_args = [
        ast.arg('self')
    ]
    for (prop_name, dtype) in prop_args:
        print(dtype)
        target = ast.Attribute(value=ast.Name("self", ctx=ast.Load()), attr=prop_name, ctx=ast.Load())
        assign = ast.Assign(targets=[target], value=ast.Name(prop_name, ctx=ast.Load()), lineno=0, col_offset=0)
        constructor_body.append(assign)

        # TODO: need to get the datatype here
        #print(ast.dump(ast.unparse(dtype)))
        arg = ast.arg(prop_name, annotation=ast.Name(id=dtype.__name__, ctx=ast.Load()))
        constructor_args.append(arg)

    args = ast.arguments(posonlyargs=[], args=constructor_args, kwonlyargs=[], defaults=[])

    classbody = [
        ast.FunctionDef(
            "__init__", args, body=constructor_body, decorator_list=[], lineno=0, col_offset=0
        ),
    ]

    classdef = ast.ClassDef(name, bases=[ast.Name('EntityProperty', ctx=ast.Load())], keywords=[], starargs=[], kwargs=[], body=classbody, decorator_list=[])
    #
    m = ast.Module(body=[classdef], lineno=0, col_offset=0, type_ignores=[])
    print(ast.unparse(m))
    exec(compile(ast.unparse(m), '<string>', 'exec'))
    return locals()[name]
