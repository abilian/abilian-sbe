(function(factory) {
    'use strict';
    define('SBEFolderEditSetup',
           ['Abilian', 'jquery'],
           factory);
}
 (function(Abilian, $) {
     'use strict';

     function setupModalFolderInputnameCheck(modal, object_id, action) {
         var $submit = modal.find('button.btn-primary'),
             $input = modal.find('input[name="title"]'),
             checkUrl = $input.data('check-url'),
             $help_span = $input.next('span.help-block'),
             $control_group = $input.closest('div.form-group');

         $submit.on('click', function(e) {
             var title = $input.val();
             $.ajax(
                 checkUrl,
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
     }

     return setupModalFolderInputnameCheck;
 }));
