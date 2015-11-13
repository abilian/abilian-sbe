/* jshint camelcase: false */
(function() {
    'use strict';

function setupFolderModal(Abilian, $) {

    {%- if doc %}
    // Simple document viewer...
    function setupDocumentViewer() {
        var imgSrc = $("img.preview").attr("src"),
            previewNav = $(".preview-nav"),
            previewPrev = $('.preview-prev'),
            previewNext = $('.preview-next');

        function showNav() {
            $(document).bind("keydown", keyDown);
            previewNav.stop().fadeTo(150, 1);
        }

        function hideNav() {
            $(document).unbind("keydown", keyDown);
            previewNav.stop().fadeTo(150, 0);
        }

        var page_num = {{ doc.page_num }};
        if (page_num > 1) {
            $("div.preview").hover(showNav, hideNav);
        }

        // TODO: what if we want to go past the last page?
        function loadNext() {
            var img = $("img.preview");
            var page = img.data("page") + 1;
            if (page >= page_num) {
                page = page - 1;
            }
            img.attr("src", imgSrc + "&page=" + page);
            img.data("page", page);
            return true;
        }

        function loadPrev() {
            var img = $("img.preview");
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

    Abilian.fn.onAppInit(function() {
        setupDocumentViewer();

    });
    {%- endif %}

}
    require(['Abilian', 'jquery'], setupFolderModal);
}());
