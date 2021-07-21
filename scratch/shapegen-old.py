import jinja2
from dataclasses import dataclass
from typing import Optional, Union, Any
import rdflib

class EntityProperty:
    pass

def add_property_to_eprop(target, propname, dtypes=None):
    def f(self, ent: EntityProperty):
        if not hasattr(self, propname):
            # TODO: add type assert?
            self._properties.append(propname)
            setattr(self, propname, [])
        if dtypes is not None and len(dtypes):
            assert isinstance(ent, dtypes), f"EntityProperty {ent} must have type {dtypes} to be used as object of {propname}"
        getattr(self, propname).append(ent)
    setattr(target, f"add_{propname}", f)

t = jinja2.Template("""
class {{ shape_name }}(EntityProperty):
    {% set comma = joiner(",") %}
    def __init__(self, {% for (name, type) in shape_props %}{{ comma() }}{{ name }}: {{ type }} {% endfor %}):
        {% for (name, _) in shape_props %}
        self.{{ name }} = {{ name }}
        {% endfor %}
""")

lookup = {
    rdflib.URIRef: 'rdflib.URIRef',
    float: 'float',
    str: 'str',
}

def get_type(defn):
    """
    if not 'required', wrap in Optional

    'datatype': -> return datatype
    'classtype': -> return typing.Union[list of Python classes]
    'enuM_vals': -> return type of an enum value, then assert membership

    returns a *string* version of a Python type annotation
    """
    optional = defn.get('required', False) == False

    # here comes the walrus
    if dtype := defn.get('datatype'):
        if optional:
            return f"Optional[{dtype}]"
        return dtype
    elif classtypes := defn.get('classtype'):
        print("HANDLE PYTHON CLASS", classtypes)
    elif enums := defn.get('enum_vals'):
        etype = lookup.get(type(enums[0]), "Any")
        if optional:
            return f"Optional[{etype}]"
        return etype



def make_shape_class(shape_name, defn):
    """
    defn is of form:
        {
            prop_name (str): {
                classtype: [<rdflib.URIRef of class>], (opt)
                datatype: <python type>, (opt)
                enum_vals: [<rdflib.URIRef> or <python value>]
                required: <bool>
            },
        }
    """
    prop_tuples = []
    # do 'value' first if it exists
    if 'value' in defn:
        value_def = defn.pop('value')
        prop_tuples.append(('value', get_type(value_def)))
    for prop_name, value_def in defn.items():
        prop_tuples.append((prop_name, get_type(value_def)))

    args = {
        'shape_name': shape_name,
        'shape_props': prop_tuples,
    }
    print(t.render(**args))
    exec(compile(t.render(**args), '<string>', 'exec'), globals(), locals())
    return locals()[shape_name]

x = {
    "value": {
        "required": True,
        "datatype": "float"
    },
    "hasUnit": {
        "required": True,
        "enum_vals": ["a", "b"],
    },
}

kls = make_shape_class("CoolingCapacityShape", x)
print(kls)
