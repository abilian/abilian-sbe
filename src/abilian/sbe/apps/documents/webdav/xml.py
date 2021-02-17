"""Parses and produces XML documents specified by the standard."""
from typing import Any, List

from lxml import etree, objectify
from lxml.builder import ElementMaker
from lxml.etree import _Element

E = ElementMaker(namespace="DAV:")


class Propfind:
    def __init__(self, xml: bytes = b"") -> None:
        self.mode = ""
        self.prop_names: List[str] = []

        if not xml:
            xml = b"<D:propfind xmlns:D='DAV:'><D:allprop/></D:propfind>"
        self.parse(xml)

    def parse(self, xml: bytes) -> None:
        root = objectify.fromstring(xml)

        child = root.getchildren()[0]
        self.mode = child.tag[len("{DAV:}") :]

        if self.mode == "prop":
            for prop in child.getchildren():
                self.prop_names.append(prop.tag)


class MultiStatus:
    def __init__(self) -> None:
        self.responses: List[Response] = []

    def add_response_for(self, href: str, obj: Any, property_list: List[str]) -> None:
        response = Response(href, obj, property_list)
        self.responses.append(response)

    def to_string(self) -> bytes:
        return etree.tostring(self.to_xml(), pretty_print=True)

    def to_xml(self) -> _Element:
        xml = E.multistatus()
        for response in self.responses:
            xml.append(response.to_xml())
        return xml


class Response:
    def __init__(self, href: str, obj: Any, property_list: List[str]) -> None:
        self.href = href
        self.property_list = property_list
        self.obj = obj

    def to_xml(self) -> _Element:
        obj = self.obj
        props = E.prop()
        for property_name in self.property_list:
            if property_name == "creationdate":
                props.append(E.creationdate("1997-12-01T17:42:21-08:00"))
            elif property_name == "displayname":
                props.append(E.displayname(obj.name))
            elif property_name == "resourcetype":
                if obj.is_folder:
                    props.append(E.resourcetype(E.collection()))
                else:
                    props.append(E.resourcetype())

        return E.response(
            E.href(self.href), E.propstat(props), E.status("HTTP/1.1 200 OK")
        )
