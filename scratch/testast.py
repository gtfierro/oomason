import ast
from rdflib import URIRef

e = """class CoolingCapacityShape:
    def __init__(self, hasUnit: rdflib.URIRef, value: float):
        self.hasUnit = hasUnit
        self.value = value
"""
print(ast.dump(ast.parse(e)))
print(ast.dump(ast.parse("rdflib.URIRef")))

x = {
    "name": "CoolingCapacityShape",
    "args": [
        ("hasUnit", URIRef),
        ("value", float)
    ],
}

constructor_body = []
constructor_args = [
    ast.arg('self')
]
for (prop_name, dtype) in x['args']:
    target = ast.Attribute(value=ast.Name("self", ctx=ast.Load()), attr=prop_name, ctx=ast.Load())
    assign = ast.Assign(targets=[target], value=ast.Name(prop_name, ctx=ast.Load()), lineno=0, col_offset=0)
    constructor_body.append(assign)

    arg = ast.arg(prop_name, annotation=ast.Name(id=dtype.__name__, ctx=ast.Load()))
    constructor_args.append(arg)

args = ast.arguments(posonlyargs=[], args=constructor_args, kwonlyargs=[], defaults=[])

classbody = [
    ast.FunctionDef(
        "__init__", args, body=constructor_body, decorator_list=[], lineno=0, col_offset=0
    ),
]

classdef = ast.ClassDef(x['name'], bases=[], keywords=[], starargs=[], kwargs=[], body=classbody, decorator_list=[])
#
m = ast.Module(body=[classdef], lineno=0, col_offset=0, type_ignores=[])
print(ast.unparse(m))
exec(compile(ast.unparse(m), '<string>', 'exec'))

x = CoolingCapacityShape(1,2)
print(x)

#compile(m, '<string>', 'exec')
