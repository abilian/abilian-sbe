from unittest import TestCase

from ..cmis.parser import Entry

XML_ENTRY = """\
<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
  xmlns:app="http://www.w3.org/2007/app"
  xmlns:cmisra="http://docs.oasis-open.org/ns/cmis/restatom/200908/">
  <cmisra:object xmlns:cmis="http://docs.oasis-open.org/ns/cmis/core/200908/">
    <cmis:properties>
      <cmis:propertyString propertyDefinitionId="cmis:name">
        <cmis:value>Toto Titi</cmis:value>
      </cmis:propertyString>
      <cmis:propertyId propertyDefinitionId="cmis:objectTypeId">
        <cmis:value>cmis:folder</cmis:value>
      </cmis:propertyId>
    </cmis:properties>
  </cmisra:object>
  <title>Toto Titi</title>
</entry>
"""

XML_ENTRY_WITH_CONTENT = """\
<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
  xmlns:app="http://www.w3.org/2007/app"
  xmlns:cmisra="http://docs.oasis-open.org/ns/cmis/restatom/200908/">
  <cmisra:content>
    <cmisra:mediatype>text/plain</cmisra:mediatype>
    <cmisra:base64>VGVzdCBjb250ZW50IHN0cmluZw==</cmisra:base64>
  </cmisra:content>
  <cmisra:object
    xmlns:cmis="http://docs.oasis-open.org/ns/cmis/core/200908/">
    <cmis:properties>
      <cmis:propertyString propertyDefinitionId="cmis:name">
        <cmis:value>testDocument</cmis:value>
      </cmis:propertyString>
      <cmis:propertyId propertyDefinitionId="cmis:objectTypeId">
        <cmis:value>cmis:document</cmis:value>
      </cmis:propertyId>
    </cmis:properties>
  </cmisra:object>
  <title>testDocument</title>
</entry>
"""


class ParserTestCase(TestCase):

  def test_folder_entry(self):
    e = Entry(XML_ENTRY)
    self.assertEquals(e.name, "Toto Titi")
    self.assertEquals(e.type, "cmis:folder")

  def test_document_entry(self):
    e = Entry(XML_ENTRY_WITH_CONTENT)
    self.assertEquals(e.name, "testDocument")
    self.assertEquals(e.type, "cmis:document")
    self.assertEquals(e.content, "Test content string")
