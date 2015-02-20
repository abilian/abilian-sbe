/* jshint camelcase: false */
(function($) {
    'use strict';

 var setup_modal_folder_inputname_check  = function(modal, object_id, action) {
     var $submit = modal.find('button.btn-primary');
     var $input = modal.find('input[name="title"]');
     var $help_span = $input.next('span.help-block');
     var $control_group = $input.closest('div.form-group');

     $submit.on('click', function(e) {
                    var title = $input.val();
                    $.ajax('{{ url_for(".check_valid_name", community_id=g.community.slug) }}',
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

    Abilian.fn.onAppInit(function() {
        setup_modal_folder_inputname_check($('#modal-edit'),
                                           '{{ doc.id if doc else folder.id }}',
                                           '{%- if doc %}document{% else %}folder{% endif %}-edit');
        setup_modal_folder_inputname_check($('#modal-new-folder'), '{{ folder.id }}', 'new');

        $('#modal-edit input[type="text"]').preventEnterKey();
        $('#modal-new-folder input[type="text"]').preventEnterKey();
    });

}(jQuery));
