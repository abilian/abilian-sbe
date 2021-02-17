define("SBEDocumentViewerSetup", ["Abilian", "jquery"], (Abilian, $) => {
  "use strict";
  function setupDocumentViewer() {
    const container = $(".preview-container");
    const img = container.find("img.preview");
    const imgSrc = img.attr("src");
    const previewPrev = container.find(".preview-prev");
    const previewNext = container.find(".preview-next");
    const pageNum = container.data("pageNum");

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
      let page = img.data("page") + 1;
      if (page >= pageNum) {
        page = page - 1;
      }
      img.attr("src", imgSrc + "&page=" + page);
      img.data("page", page);
      return true;
    }

    function loadPrev() {
      let page = img.data("page") - 1;
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
      const code = e.keyCode;
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
