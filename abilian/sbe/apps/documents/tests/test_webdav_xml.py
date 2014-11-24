from unittest import TestCase
from os.path import dirname

from lxml import etree

from ..webdav.xml import Propfind, MultiStatus
from ..webdav.constants import DAV_PROPS


class PropfindTestCase(TestCase):

  def test_sample1(self):
    xml = open(dirname(__file__) + "/data/propfind1.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'prop'

  def test_sample2(self):
    xml = open(dirname(__file__) + "/data/propfind2.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'prop'

  def test_sample3(self):
    xml = open(dirname(__file__) + "/data/propfind3.xml").read()
    propfind = Propfind(xml)
    assert propfind.mode == 'allprop'


class MultiStatusTestCase(TestCase):

  def test_empty_multistatus(self):
    m = MultiStatus()
    result = m.to_string()

    # Check XML is weel-formed
    etree.fromstring(result)

  def test(self):
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
