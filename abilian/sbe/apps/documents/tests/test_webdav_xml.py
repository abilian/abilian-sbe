# coding=utf-8
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pathlib import Path

from lxml import etree

from ..webdav.constants import DAV_PROPS
from ..webdav.xml import MultiStatus, Propfind


def test_propfind_sample1():
    xml = (Path(__file__).parent / "data" / "propfind1.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample2():
    xml = (Path(__file__).parent / "data" / "propfind2.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "prop"


def test_propfind_sample3():
    xml = (Path(__file__).parent / "data" / "propfind3.xml").open("rb").read()
    propfind = Propfind(xml)
    assert propfind.mode == "allprop"


def test_empty_multistatus():
    m = MultiStatus()
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)


def test_multistatus():
    class Obj(object):
        pass

    obj = Obj()
    obj.name = "some name"
    obj.is_folder = True
    m = MultiStatus()
    m.add_response_for("http://example.com/", obj, DAV_PROPS)
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)
