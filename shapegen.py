import jinja2
from dataclasses import dataclass
from typing import Optional, Union, Any
import rdflib
from upper import Unit, Entity, EntityProperty
from rdflib import XSD, BNode


t = jinja2.Template("""
@dataclass
class {{ shape_name }}(EntityProperty):
    {% for (name, type) in shape_props %}
    {{ name }}: {{ type }}
    {% endfor %}

    {% if possible_values %}
    possible_values = {{ possible_values }}
    {% endif %}

    {% if possible_units %}
    possible_units = {{ possible_units }}
    {% endif %}

    def __post_init__(self):
        self.URI = BNode()
        self.classURI = rdflib.URIRef("{{ shape }}")
        EntityProperty._instances.append(self)
        
""")

prop_lookup = {}

lookup = {
    rdflib.URIRef: 'rdflib.URIRef',
    XSD['float']: 'float',
    XSD['integer']: 'int',
    XSD['string']: 'str',
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
        dtype = lookup.get(dtype, dtype)
        if optional:
            return f"Optional[{dtype}]"
        return dtype
    elif classtypes := defn.get('classtype'):
        cnames = [x.split('#')[-1] for x in classtypes]
        cnames = f"Union[{','.join(cnames)}]"
        return "Any"
        # TODO: how to handle if not defined yet
        #if optional:
        #    return f"Optional[{cnames}]"
        #return cnames
        #raise Exception("HANDLE PYTHON CLASS", classtypes)
    elif enums := defn.get('enum_vals'):
        etype = lookup.get(type(enums[0]), "Any")
        if optional:
            return f"Optional[{etype}]"
        return etype

def get_val(thing):
    if isinstance(thing, rdflib.Literal):
        return thing.toPython()
    return thing

def make_shape_class(shape, defn):
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
    shape_name = shape.split('#')[-1]
    args = {
        'shape': shape,
        'shape_name': shape_name,
        'shape_props': [],
    }
    # rewrite property names
    prop_names = list(defn.keys())[:]
    for prop_name in prop_names:
        new_name = prop_name.split('#')[-1]
        prop_lookup[new_name] = prop_name
        defn[new_name] = defn.pop(prop_name)
    # do 'value' first if it exists
    if 'value' in defn:
        value_def = defn.pop('value')
        if 'enum_vals' in value_def:
            args['possible_values'] = [get_val(x) for x in value_def['enum_vals']]
        args['shape_props'].append(('value', get_type(value_def)))
    if 'hasUnit' in defn:
        value_def = defn.pop('hasUnit')
        if 'enum_vals' in value_def:
            args['possible_units'] = [get_val(x) for x in value_def['enum_vals']]
        args['shape_props'].append(('hasUnit', "Unit"))
    for prop_name, value_def in defn.items():
        args['shape_props'].append((prop_name, get_type(value_def)))

    #print(t.render(**args))
    exec(compile(t.render(**args), '<string>', 'exec'), globals(), locals())
    return locals()[shape_name]


if __name__ == '__main__':
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
