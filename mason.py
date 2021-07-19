import rdflib
import brickschema
from brickschema import namespaces as ns
from typing import Optional

class Entity:
    _class_label = "Brick Entity"
    _definition = ""

    _all_entities = []

    def __init__(self, URI: rdflib.URIRef, label: Optional[str] = None):
        self.URI = URI
        self.entity_label = label
        self._properties = []
        self._all_entities.append(self)

    @property
    def class_label(self):
        return str(self._class_label)

    @property
    def definition(self):
        return str(self._definition)


class BrickClassGenerator:
    _propname_lookup = {}

    def __init__(self, brick_graph: Optional[rdflib.Graph] = None):
        if brick_graph is not None:
            self.graph = brick_graph
        else:
            self.graph = brickschema.Graph(load_brick_nightly=True)

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

        self.Point = type(
                "Point",
                (Entity,),
                {"classURI": ns.BRICK["Point"], "_class_label": "Point", "__repr__": _brick_repr},
            )
        self._build_subclasses(self.Point, set())

        self.Location = type(
                "Location",
                (Entity,),
                {"classURI": ns.BRICK["Location"], "_class_label": "Location", "__repr__": _brick_repr},
            )
        self._build_subclasses(self.Location, set())


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
        for (prop, dom, _rng) in res:
            propname = prop.split('#')[-1]
            self._propname_lookup[propname] = prop
            if dom is not None:
                domclass = dom.split('#')[-1]
                if hasattr(self, domclass):
                    add_property_to_class(getattr(self, domclass), propname)
            else:
                add_property_to_class(Entity, propname)


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
            self._build_subclasses(klass,  visited=visited)



def add_property_to_class(target, propname):
    def f(self, ent: Entity):
        if not hasattr(self, propname):
            self._properties.append(propname)
            setattr(self, propname, [])
        getattr(self, propname).append(ent)
    setattr(target, f"add_{propname}", f)


def _brick_repr(self):
    return f"<BRICK {self._class_label}: {self.URI}>"


def compile_model(binds):
    g = brickschema.Graph()
    for (pfx, ns) in binds:
        g.bind(pfx, ns)
    for ent in Entity._all_entities:
        g.add((ent.URI, ns.A, ent.classURI))
        for propname in ent._properties:
            prop = BrickClassGenerator._propname_lookup[propname]
            for propval in getattr(ent, propname):
                g.add((ent.URI, prop, propval.URI))
    valid, _, report = g.validate()
    if not valid:
        raise Exception(report)
    return g

Brick = BrickClassGenerator()
Brick11 = BrickClassGenerator(brickschema.Graph(brick_version="1.1"))
Brick12 = BrickClassGenerator(brickschema.Graph(brick_version="1.2"))

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

    graph = compile_model([
        ("bldg", BLDG)
    ])
    graph.serialize("output.ttl", format="ttl")
