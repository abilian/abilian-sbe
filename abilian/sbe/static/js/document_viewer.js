(function(factory) {
    'use strict';
    define('SBEDocumentViewerSetup',
           ['Abilian', 'jquery'],
           factory);
}
 (function(Abilian, $) {
     'use strict';

     function setupDocumentViewer() {
         var container = $('.preview-container'),
             img = container.find('img.preview'),
             imgSrc = img.attr('src'),
             previewNav = container.find('.preview-nav'),
             previewPrev = container.find('.preview-prev'),
             previewNext = container.find('.preview-next'),
             pageNum = container.data('pageNum');

         function showNav() {
             $(document).bind('keydown', keyDown);
             previewNav.stop().fadeTo(150, 1);
         }

         function hideNav() {
             $(document).unbind('keydown', keyDown);
             previewNav.stop().fadeTo(150, 0);
         }

         if (pageNum > 1) {
             container.hover(showNav, hideNav);
         }

         // TODO: what if we want to go past the last page?
         function loadNext() {
             var page = img.data('page') + 1;
             if (page >= pageNum) {
                 page = page - 1;
             }
             img.attr('src', imgSrc + '&page=' + page);
             img.data('page', page);
             return true;
         }

         function loadPrev() {
             var page = img.data('page') - 1;
             if (page < 0) {
                 page = 0;
             }
             img.attr('src', imgSrc + '&page=' + page);
             img.data('page', page);
             return true;
         }

         previewNext.click(loadNext);
         previewPrev.click(loadPrev);

         function keyDown(e) {
             var code = e.keyCode;
             // Note: we prevent default keyboard action
             if (code == 39) {
                 loadNext();
                 return false;
             } else if (code == 37) {
                 loadPrev();
                 return false;
             }
             return true;
         }
     }

     return setupDocumentViewer;
}));
