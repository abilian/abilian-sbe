/* datatable: sort types and filters */
require(["jquery", "jquery.dataTables"], ($) => {
  "use strict";
  const FOLDER_TYPE = "abilian.sbe.apps.documents.models.folder";

  function sortFolderFirstCmp(x, y) {
    if (x === y) {
      return 0;
    }
    if (x === FOLDER_TYPE) {
      return -1;
    }
    if (y === FOLDER_TYPE) {
      return 1;
    }
    return 0;
  }

  $.extend($.fn.dataTableExt.oSort, {
    "cmistype-pre": $.fn.dataTableExt.oSort["string-pre"],
    "cmistype-asc": sortFolderFirstCmp,
    "cmistype-desc": sortFolderFirstCmp,
  });
});
