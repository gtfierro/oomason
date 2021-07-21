import rdflib
from collections import defaultdict
import re
import ast
from enum import Enum
import brickschema
from brickschema import namespaces as ns
from typing import Optional
import shapegen
from upper import Unit, Entity, EntityProperty

def rev(s):
    return ''.join(reversed(s))

def make_enum(enum_name, enum_vals):
    vals = []
    for val in enum_vals:
        if isinstance(val, rdflib.URIRef):
            key, ns = re.split(r':|#|/', rev(str(val)), 1)
            key = rev(key)
            vals.append((key, val))
        elif isinstance(val, rdflib.Literal):
            val = str(val)
            vals.append((val, val))
    return Enum(enum_name, vals)


class placeholder:
    pass

class BrickClassGenerator:
    _propname_lookup = {}
    _classname_lookup = {}
    EntityProperty = placeholder()
    Unit = placeholder()

    def __init__(self, brick_graph: Optional[rdflib.Graph] = None):
        if brick_graph is not None:
            self.graph = brick_graph
        else:
            self.graph = brickschema.Graph(load_brick_nightly=True)
        self.graph.parse("http://qudt.org/vocab/unit/", format="ttl")

        self._build_equipment()
        self._build_points()
        self._build_locations()
        self._build_units()
        self._build_shapes()

        self._build_shape_class(ns.BRICK["CoolingCapacityShape"])

        # get possible relationships
        res = self.graph.query("""SELECT ?prop ?dom ?rng WHERE {
            ?prop   a   owl:ObjectProperty .
            OPTIONAL { ?prop rdfs:domain ?dom } .
            OPTIONAL { ?prop rdfs:range ?rng } .
        }""")
        # TODO: to use 'rng' we would need to figure out dynamic type annotations
        for (prop, dom, _rng) in res:
            propname = prop.split('#')[-1]
            self._propname_lookup[propname] = prop
            if dom is not None:
                domclass = dom.split('#')[-1]
                if hasattr(self, domclass):
                    add_property_to_class(getattr(self, domclass), propname)
            else:
                add_property_to_class(Entity, propname)


        res = self.graph.query("""SELECT ?path ?cls ?allowed WHERE {
            ?sh a sh:NodeShape .
            ?sh sh:targetClass ?cls .
            ?sh sh:property ?prop .
            ?prop sh:path ?path .
            {
                ?prop sh:class ?allowed
            }
            UNION
            {
                ?prop sh:or/rdf:rest*/rdf:first/sh:class ?allowed
            }
        }""")
        prop_defs = defaultdict(lambda : defaultdict(set))

        for (prop, dom, rng) in res:
            propname = prop.split('#')[-1]
            prop_defs[propname]['dom'].add(dom)
            prop_defs[propname]['rng'].add(rng)
            self._propname_lookup[propname] = prop

        # get possible entity properties
        res = self.graph.query("""SELECT ?prop ?dom ?rng WHERE {
            ?prop   a   brick:EntityProperty .
            OPTIONAL { ?prop rdfs:domain ?dom } .
            OPTIONAL { ?prop rdfs:range ?rng } .
        }""")
        for (prop, dom, rng) in res:
            propname = prop.split('#')[-1]
            prop_defs[propname]['dom'].add(dom)
            prop_defs[propname]['rng'].add(rng)
            self._propname_lookup[propname] = prop

        for prop, defn in prop_defs.items():
            domains = []
            for dom in defn.get('dom', []):
                if not dom:
                    continue
                domclass = dom.split('#')[-1]
                domains.append(getattr(self, domclass))
            if not len(domains):
                domains.append(Entity)

            ranges = []
            for rng in defn.get('rng', []):
                if not rng:
                    continue
                # TODO: needs the shape classes to exist
                rngclass = self._classname_lookup.get(rng)
                if rngclass:
                    ranges.append(rngclass)

            for dom in domains:
                add_property_to_class(dom, prop, dtypes=tuple(ranges))
            # if no domain? add to all Entities
            if len(domains) == 0:
                add_property_to_class(Entity, prop, dtypes=tuple(ranges))


    def _build_subclasses(self, rootclass, visited=None):
        if rootclass.classURI in visited:
            return
        visited.add(rootclass.classURI)
        res = self.graph.query(
            f"""SELECT ?class ?label ?defn WHERE {{
            ?class rdfs:subClassOf <{rootclass.classURI}> .
            OPTIONAL {{ ?class rdfs:label ?label }} .
            OPTIONAL {{ ?class skos:definition ?defn }} .
        }}"""
        )
        for row in res:
            (uri, label, defn) = row
            name = uri.split("#")[-1]
            klass = type(
                name,
                (rootclass,),
                {
                    "classURI": uri,
                    "__repr__": _brick_repr,
                },
            )
            if label is not None:
                klass._class_label = label
            if defn is not None:
                klass._definition = defn
                klass.__doc__ = defn
            setattr(self, name, klass)
            self._classname_lookup[rootclass] = klass
            self._build_subclasses(klass,  visited=visited)


    def _build_equipment(self):
        # construct initial Equipment class
        self.Equipment = type(
                "Equipment",
                (Entity,),
                {
                    "classURI": ns.BRICK["Equipment"],
                    "_class_label": "Equipment",
                    "__repr__": _brick_repr,
                },
            )
        # construct subclasses recursively
        self._build_subclasses(self.Equipment, set())
        self._classname_lookup[ns.BRICK['Equipment']] = self.Equipment

    def _build_points(self):
        self.Point = type(
                "Point",
                (Entity,),
                {"classURI": ns.BRICK["Point"], "_class_label": "Point", "__repr__": _brick_repr},
            )
        self._build_subclasses(self.Point, set())
        self._classname_lookup[ns.BRICK['Point']] = self.Point

    def _build_locations(self):
        self.Location = type(
                "Location",
                (Entity,),
                {"classURI": ns.BRICK["Location"], "_class_label": "Location", "__repr__": _brick_repr},
            )
        self._build_subclasses(self.Location, set())
        self._classname_lookup[ns.BRICK['Location']] = self.Location

    def _build_units(self):
        res = self.graph.query("""SELECT ?unit ?symbol ?label ?expr ?defn WHERE {
            ?unit a  qudt:Unit .
            ?unit rdfs:label ?label .
            OPTIONAL {?unit qudt:symbol ?symbol } .
            OPTIONAL {?unit qudt:expression ?expr } .
            OPTIONAL { ?unit dcterms:description ?defn }
        }""")
        for (unit, symbol, label, expr, defn) in res:
            inst = Unit()
            inst._uri = unit
            if symbol is not None:
                inst._symbol = symbol
            elif expr is not None:
                inst._symbol = f"${expr}$"
            inst._name = label
            inst._defn = defn
            safe_name = label.replace(' ', '_')
            safe_name = safe_name.replace('^', 'exp')
            safe_name = safe_name.replace('(','').replace(')','')
            setattr(self.Unit, safe_name, inst)


    def _build_shapes(self):
        res = self.graph.query("""SELECT ?shape WHERE {
            ?shape  a   sh:NodeShape .
            ?prop   rdfs:range ?shape .
            ?prop   a   brick:EntityProperty 
        }""")
        for (shape,) in res:
            self._build_shape_class(shape)


    # TODO: how to handle shapes?
    def _build_shape_class(self, shape):
        res = self.graph.query(f"""SELECT ?path ?min ?enum ?datatype ?class WHERE {{
            <{shape}> sh:property ?prop .
            ?prop sh:path ?path .
            OPTIONAL {{ ?prop sh:in/rdf:rest*/rdf:first ?enum }} .
            OPTIONAL {{ ?prop sh:datatype ?datatype }} .
            OPTIONAL {{ ?prop sh:class ?class }} .
            OPTIONAL {{ ?prop sh:minCount ?min }}
        }}""")
        shape_name = shape.split('#')[-1]
        props = {}
        for (path, mincount, enum, datatype, classtype) in res:
            if path not in props:
                props[path] = {"enum_vals": []}

            if enum is not None:
                props[path]['enum_vals'].append(enum)

            if datatype is not None:
                props[path]['datatype'] = datatype

            if classtype is not None:
                if 'classtype' not in props[path]:
                    props[path]['classtype'] = []
                props[path]['classtype'].append(classtype)

            if datatype is not None:
                props[path]['datatype'] = datatype
            if mincount is None:
                props[path]['required'] = False
            elif int(mincount) > 0:
                props[path]['required'] = True
            else:
                props[path]['required'] = False


        attrs = {}
        prop_args = []
        for(prop, defn) in props.items():
            prop_name = prop.split('#')[-1]
            if len(defn['enum_vals']) > 0:
                enum = make_enum(prop_name, defn['enum_vals'])
                setattr(self, prop_name, enum)
                attrs[prop_name] = enum
                prop_args.append((prop_name, type(defn['enum_vals'][0])))
            elif 'datatype' in defn:
                prop_args.append((prop_name, rdflib.URIRef))
            else:
                prop_args.append((prop_name, rdflib.URIRef))
        kls = shapegen.make_shape_class(shape, props)
        string_name = shape_name.split('#')[-1]
        setattr(self.EntityProperty, string_name, kls)



# TODO: handle dtype (need to handle *lists* of possible dtypes)
def add_property_to_class(target, propname, dtypes=None):
    def f(self, ent: Entity):
        if not hasattr(self, propname):
            # TODO: add type assert?
            self._properties.append(propname)
            setattr(self, propname, [])
        if dtypes is not None and len(dtypes):
            assert isinstance(ent, dtypes), f"Entity {ent} must have type {dtypes} to be used as object of {propname}"
        getattr(self, propname).append(ent)
    setattr(target, f"add_{propname}", f)


def _brick_repr(self):
    return f"<BRICK {self._class_label}: {self.URI}>"


def compile_model(binds):
    g = brickschema.Graph()
    for (pfx, namespace) in binds:
        g.bind(pfx, namespace)
    for ent in Entity._all_entities:
        g.add((ent.URI, ns.A, ent.classURI))
        for propname in ent._properties:
            prop = BrickClassGenerator._propname_lookup[propname]
            for propval in getattr(ent, propname):
                g.add((ent.URI, prop, propval.URI))
    for ep in shapegen.EntityProperty._instances:
        g.add((ep.URI, ns.A, ep.classURI))
        for prop_name in ep.__annotations__.keys():
            val = getattr(ep, prop_name)
            if isinstance(val, (Entity, EntityProperty, Unit)):
                g.add((ep.URI, shapegen.prop_lookup[prop_name], val.URI))
            elif isinstance(val, rdflib.URIRef):
                g.add((ep.URI, shapegen.prop_lookup[prop_name], val))
            else:
                g.add((ep.URI, shapegen.prop_lookup[prop_name], rdflib.Literal(val)))

    valid, _, report = g.validate()
    if not valid:
        raise Exception(report)
    return g

g = brickschema.Graph().load_file("Brick.ttl")
Brick = BrickClassGenerator(g)
#Brick11 = BrickClassGenerator(brickschema.Graph(brick_version="1.1"))
#Brick12 = BrickClassGenerator(brickschema.Graph(brick_version="1.2"))

if __name__ == '__main__':
    BLDG = rdflib.Namespace("example#")

    ahu1 = Brick.AHU(BLDG["ahu1"], "ahu #1")

    vav1 = Brick.VAV(BLDG["vav1"], "vav #1")
    tsen1 = Brick.Supply_Air_Temperature_Sensor(BLDG["sat1"])
    tsp1 = Brick.Supply_Air_Temperature_Setpoint(BLDG["sp1"])
    vav1.add_hasPoint(tsen1)
    vav1.add_hasPoint(tsp1)

    vav2 = Brick.VAV(BLDG["vav2"], "vav #2")
    tsen2 = Brick.Supply_Air_Temperature_Sensor(BLDG["sat2"])
    tsp2 = Brick.Supply_Air_Temperature_Setpoint(BLDG["sp2"])
    vav2.add_hasPoint(tsen2)
    vav2.add_hasPoint(tsp2)

    ahu1.add_feeds(vav1)
    ahu1.add_feeds(vav2)
    for isfed in ahu1.feeds:
        print(f"{ahu1} feeds {isfed}")

    bldg = Brick.Building(BLDG["mysite"], "Soda Hall")
    bldg.add_isLocationOf(ahu1)
    bldg.add_isLocationOf(vav1)
    bldg.add_isLocationOf(vav2)

    fl1 = Brick.Floor(BLDG["floor1"], "Floor 1")
    bldg.add_hasPart(fl1)
    rm1 = Brick.Room(BLDG["room1"], "Room 1")
    fl1.add_hasPart(rm1)
    rm1.add_area(Brick.EntityProperty.AreaShape(10, Brick.Unit.Quad))

    graph = compile_model([
        ("bldg", BLDG)
    ])
    graph.serialize("output.ttl", format="ttl")

    kls = Brick._build_shape_class(ns.BRICK["CoolingCapacityShape"])

    p = Brick.Temperature_Sensor(BLDG['bad_sensor'])
    try:
        bldg.add_hasPart(p) # this will throw an assertion error
    except AssertionError as e:
        print("Successfully caught bad model!")
        print(e)
