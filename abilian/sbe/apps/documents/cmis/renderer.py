from flask import render_template

# TEMP
ROOT = "http://localhost:5000/cmis/atompub"
XML_HEADER = "<?xml version='1.0' encoding='UTF-8'?>\n"


class Feed(object):
  def __init__(self, object, collection):
    self.object = object
    self.collection = collection

  def to_xml(self, **options):
    args = {'ROOT': ROOT, 'object': self.object,
            'collection': self.collection, 'to_xml': to_xml}
    return render_template("cmis/feed.xml", **args)


class Entry(object):
  def __init__(self, obj):
    self.obj = obj

  def to_xml(self, **options):
    args = {'ROOT': ROOT, 'folder': self.obj, 'document': self.obj,
            'options': options, 'to_xml': to_xml}

    if self.obj.sbe_type == 'cmis:folder':
      result = render_template("cmis/folder.xml", **args)
    elif self.obj.sbe_type == 'cmis:document':
      result = render_template("cmis/document.xml", **args)
    else:
      raise Exception("Unknown base object type: %s" % self.obj.sbe_type)

    if not 'no_xml_header' in options:
      result = XML_HEADER + result

    return result


def to_xml(obj, **options):
  entry = Entry(obj)
  return entry.to_xml(**options)
