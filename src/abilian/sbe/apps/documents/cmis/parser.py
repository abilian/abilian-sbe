"""Parses XML messages and converts them to objects."""
import base64
from datetime import datetime
from typing import Dict, List

from lxml import objectify
from lxml.objectify import ObjectifiedElement

ATOM_NS = "http://www.w3.org/2005/Atom"
APP_NS = "http://www.w3.org/2007/app"
CMISRA_NS = "http://docs.oasis-open.org/ns/cmis/restatom/200908/"
CMIS_NS = "http://docs.oasis-open.org/ns/cmis/core/200908/"


class Entry:
    def __init__(self, xml: bytes = None) -> None:
        self.properties: Dict[str, Property] = {}
        self.links: List[str] = []
        self.content_type = ""
        self.content = b""

        if xml:
            self.parse(xml)

    def parse(self, xml: bytes) -> None:
        root = objectify.fromstring(xml)
        object = root["{%s}object" % CMISRA_NS]
        properties = object["{%s}properties" % CMIS_NS]
        for element in properties.iterchildren():
            property = Property(element)
            self.properties[property.property_definition_id] = property

        content_element = getattr(root, "{%s}content" % CMISRA_NS, None)
        if content_element is not None:
            self.content_type = content_element.mediatype.text
            self.content = base64.b64decode(content_element.base64.text)

    @property
    def name(self) -> str:
        return self.properties["cmis:name"].value

    @property
    def type(self) -> str:
        return self.properties["cmis:objectTypeId"].value


class Property:
    """A property MAY hold zero, one, or more typed data value(s). Each
    property MAY be single-valued or multi-valued. A single-valued property
    contains a single data value, whereas a multi-valued property contains an
    ordered list of data values of the same type. The ordering of values in a
    multi-valued property SHOULD be preserved by the repository.

    A property, either single-valued or multi-valued, MAY be in a "not set" state.
    CMIS does not support "null" property value. If a multi-valued property
    is not in a "not set" state, its property value MUST be a non-empty list of
    individual values. Each individual value in the list MUST NOT be in a "not
    set" state and MUST conform to the property's property-type.

    A multi-valued property is either set or not set in its entirety. An
    individual value of a multi-valued property MUST NOT be in an individual
    "value not set" state and hold a position in the list of values. An empty
    list of values MUST NOT be allowed.

    Every property is typed. The property-type defines the data type of the data
    value(s) held by the property. CMIS specifies the following property-types.
    """

    def __init__(self, element: ObjectifiedElement = None) -> None:
        if element is not None:
            self.parse(element)

    def parse(self, element: ObjectifiedElement) -> None:
        tag = element.tag
        self.type = tag[tag.index("}") + 1 + len("property") :].lower()
        self.property_definition_id = element.attrib["propertyDefinitionId"]
        self.local_name = element.attrib.get("localName")
        self.display_name = element.attrib.get("displayName")
        self.query_name = element.attrib.get("queryName")

        value_elem = getattr(element, "{%s}value" % CMIS_NS)
        if value_elem:
            value = value_elem.text
        else:
            self.value = value = None

        if value:
            if self.type in ("id", "string"):
                self.value = value
            elif self.type == "datetime":
                # FIXME
                self.value = datetime(value)
            else:
                raise Exception(f"Unknown value type: {self.type}")
