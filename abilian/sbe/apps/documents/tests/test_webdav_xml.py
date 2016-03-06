from os.path import dirname

from lxml import etree

from ..webdav.constants import DAV_PROPS
from ..webdav.xml import MultiStatus, Propfind


def test_propfind_sample1():
    xml = open(dirname(__file__) + "/data/propfind1.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'prop'


def test_propfind_sample2():
    xml = open(dirname(__file__) + "/data/propfind2.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'prop'


def test_propfind_sample3():
    xml = open(dirname(__file__) + "/data/propfind3.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'allprop'


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
