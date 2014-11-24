"""
Parses and produces XML documents specified by the standard.
"""

from lxml import objectify, etree
from lxml.builder import ElementMaker


E = ElementMaker(namespace="DAV:")


class Propfind(object):
  def __init__(self, xml=""):
    self.mode = ""
    self.prop_names = []

    if not xml:
      xml = "<D:propfind xmlns:D='DAV:'><D:allprop/></D:propfind>"
    self.parse(xml)

  def parse(self, xml):
    root = objectify.fromstring(xml)

    child = root.getchildren()[0]
    self.mode = child.tag[len("{DAV:}"):]

    if self.mode == "prop":
      for prop in child.getchildren():
        self.prop_names.append(prop.tag)


class MultiStatus(object):
  def __init__(self):
    self.responses = []

  def add_response_for(self, href, obj, property_list):
    response = Response(href, obj, property_list)
    self.responses.append(response)

  def to_string(self):
    return etree.tostring(self.to_xml(), pretty_print=True)

  def to_xml(self):
    xml = E.multistatus()
    for response in self.responses:
      xml.append(response.to_xml())
    return xml


class Response(object):
  def __init__(self, href, obj, property_list):
    self.href = href
    self.property_list = property_list
    self.obj = obj

  def to_xml(self):
    obj = self.obj
    props = E.prop()
    for property_name in self.property_list:
      if property_name == 'creationdate':
        props.append(E.creationdate("1997-12-01T17:42:21-08:00"))
      elif property_name == 'displayname':
        props.append(E.displayname(obj.name))
      elif property_name == 'resourcetype':
        if obj.is_folder:
          props.append(E.resourcetype(E.collection()))
        else:
          props.append(E.resourcetype())

    return E.response(E.href(self.href),
                      E.propstat(props),
                      E.status("HTTP/1.1 200 OK"))
