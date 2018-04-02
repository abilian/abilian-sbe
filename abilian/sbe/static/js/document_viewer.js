define("SBEDocumentViewerSetup", ["Abilian", "jquery"], function(Abilian, $) {
  "use strict";
  function setupDocumentViewer() {
    var container = $(".preview-container");
    var img = container.find("img.preview");
    var imgSrc = img.attr("src");
    var previewPrev = container.find(".preview-prev");
    var previewNext = container.find(".preview-next");
    var pageNum = container.data("pageNum");

    function showNav() {
      $(document).bind("keydown", keyDown);
    }

    function hideNav() {
      $(document).unbind("keydown", keyDown);
    }

    if (pageNum > 1) {
      container.hover(showNav, hideNav);
    } else {
      previewPrev.hide();
      previewNext.hide();
    }

    // TODO: what if we want to go past the last page?
    function loadNext() {
      var page = img.data("page") + 1;
      if (page >= pageNum) {
        page = page - 1;
      }
      img.attr("src", imgSrc + "&page=" + page);
      img.data("page", page);
      return true;
    }

    function loadPrev() {
      var page = img.data("page") - 1;
      if (page < 0) {
        page = 0;
      }
      img.attr("src", imgSrc + "&page=" + page);
      img.data("page", page);
      return true;
    }

    previewNext.click(loadNext);
    previewPrev.click(loadPrev);

    function keyDown(e) {
      var code = e.keyCode;
      // Note: we prevent default keyboard action
      if (code === 39) {
        loadNext();
        return false;
      }
      if (code === 37) {
        loadPrev();
        return false;
      }
      return true;
    }
  }

  return setupDocumentViewer;
});
