from __future__ import annotations

from pathlib import Path

from lxml import etree

from abilian.sbe.apps.documents.webdav.constants import DAV_PROPS
from abilian.sbe.apps.documents.webdav.xml import MultiStatus, Propfind


def test_propfind_sample1():
    xml = read_file("propfind1.xml")
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample2():
    xml = read_file("propfind2.xml")
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample3():
    xml = read_file("propfind3.xml")
    propfind = Propfind(xml)
    assert propfind.mode == "allprop"


def test_empty_multistatus():
    m = MultiStatus()
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)


def test_multistatus():
    class Obj:
        name = "some name"
        is_folder = True

    obj = Obj()
    m = MultiStatus()
    m.add_response_for("http://example.com/", obj, DAV_PROPS)
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)


def read_file(filename: str) -> bytes:
    return (Path(__file__).parent / "data" / filename).open("rb").read()
