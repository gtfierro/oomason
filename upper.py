import rdflib
from typing import Optional


class Unit:
    _uri = ""
    _name = ""
    _symbol = ""

    @property
    def URI(self):
        return self._uri

    @property
    def name(self):
        return str(self._name)

    @property
    def symbol(self):
        return str(self._symbol)

    def __repr__(self):
        return f"<Unit: {self.name}>"

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

class EntityProperty:
    _instances = []
    pass
