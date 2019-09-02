from pathlib import Path

from lxml import etree

from abilian.sbe.apps.documents.webdav.constants import DAV_PROPS
from abilian.sbe.apps.documents.webdav.xml import MultiStatus, Propfind


def test_propfind_sample1() -> None:
    xml = (Path(__file__).parent / "data" / "propfind1.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample2() -> None:
    xml = (Path(__file__).parent / "data" / "propfind2.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample3() -> None:
    xml = (Path(__file__).parent / "data" / "propfind3.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "allprop"


def test_empty_multistatus() -> None:
    m = MultiStatus()
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)


def test_multistatus() -> None:
    class Obj:
        name = "some name"
        is_folder = True

    obj = Obj()
    m = MultiStatus()
    m.add_response_for("http://example.com/", obj, DAV_PROPS)
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)
