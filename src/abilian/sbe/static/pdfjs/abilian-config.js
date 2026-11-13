/* What the viewer is to show, from the attributes on this script's own tag: the
   Content Security Policy rules out setting these in an inline script. */
(function () {
  "use strict";
  var settings = document.currentScript.dataset;
  PDFJS.workerSrc = settings.workerSrc;
  DEFAULT_URL = settings.pdfUrl;
})();
