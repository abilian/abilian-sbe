/* jshint camelcase: false */
(function() {
    'use strict';

function setupFolderModal(Abilian, $) {
    function setupModalFolderInputnameCheck(modal, object_id, action) {
        var $submit = modal.find('button.btn-primary'),
            $input = modal.find('input[name="title"]'),
            $help_span = $input.next('span.help-block'),
            $control_group = $input.closest('div.form-group');

        $submit.on('click', function(e) {
            var title = $input.val();
            $.ajax(
                '{{ url_for(".check_valid_name", community_id=g.community.slug) }}',
                { async: false,
                  cache: false,
                  data: { object_id: object_id,
                          title: title,
                          action: action },
                  success: function(data) {
                      var valid = data.valid;
                      if (!valid) {
                          e.preventDefault();
                          $control_group.addClass('has-error');
                          $help_span.text(data.help_text);
                          $help_span.removeClass('hide');
                      } else {
                          $control_group.removeClass('has-error');
                          $help_span.text('');
                          $help_span.addClass('hide');
                      }
                  }
                });
        });
    };

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
        setupModalFolderInputnameCheck(
            $('#modal-edit'),
            '{{ doc.id if doc else folder.id }}',
            '{%- if doc %}document{% else %}folder{% endif %}-edit'
        );
        setupModalFolderInputnameCheck(
            $('#modal-new-folder'),
            '{{ folder.id }}',
            'new'
        );

        $('#modal-edit input[type="text"]').preventEnterKey();
        $('#modal-new-folder input[type="text"]').preventEnterKey();

        setupDocumentViewer();
    });
}
    require(['Abilian', 'jquery'], setupFolderModal);
}());
