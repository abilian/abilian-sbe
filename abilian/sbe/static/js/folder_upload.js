(function(factory) {
    'use strict';
    define('SBEFolderUploadSetup',
           ['Abilian', 'jquery', 'FileAPI', 'jquery.fileapi'],
           factory);
}
 (function(Abilian, $, FileAPI) {
     'use strict';

     function setupModalFolderUpload(modalId, url, messages) {
         var hasErrors = false,
             formData = {action: 'upload'},
             errorMessages = {
                 fileUploadError: 'Error - File not uploaded',
                 fileTooLargeError: 'Error: maximum file size exceeded'
             };
         $.extend(errorMessages, messages || {});
         formData[Abilian.csrf_fieldname] = Abilian.csrf_token;



         function onComplete(evt, ui) {
             /* jshint unused: false */
             if (!hasErrors) {
                 location.reload();
             }
         }

         function onUploadComplete(evt, ui) {
             /* jshint validthis: true */
             var type = evt.type,
                 uid = FileAPI.uid(ui.file),
                 widget = $(this).fileapi('widget'),
                 $fileUi = widget.$file(uid),
                 $statusEl = $fileUi.find('.statusicon'),
                 $icon = $statusEl.find('.glyphicon');

             if (ui.error) {
                 var progress = $fileUi.find('.progress'),
                     errorEl = $('<span class="text-danger"></span>'),
                     errorMsg = errorMessages.fileUploadError;
                 hasErrors = true;
                 $icon.removeClass('glyphicon-upload');
                 $icon.addClass('glyphicon-warning-sign text-danger');

                 switch (ui.status) {
                 case 413: //Request Entity Too Large
                     errorMsg = errorMessages.fileTooLargeError;
                     break;
                 }
                 errorEl.text(errorMsg);
                 progress.replaceWith(errorEl);
                 return;
             }

             if (type == 'fileupload') {
                 $icon.addClass('glyphicon-upload');
                 $statusEl.removeClass('hidden');
             }
             else if (type == 'filecomplete') {
                 $icon.removeClass('glyphicon-upload');
                 $icon.addClass('glyphicon-ok');
                 $statusEl.removeClass('btn-default');
                 $statusEl.addClass('btn-success');
                 $fileUi.find('.progress .progress-bar').width('100%');
             }
         }

         $('#' + modalId)
             .fileapi({
                 multiple: true,
                 url: url,
                 data: formData,
                 dataType: null, //not JSON
                 clearOnComplete: false,
                 elements: {
                     ctrl: { upload: '.js-upload' },
                     empty: { show: '.b-upload__hint' },
                     emptyQueue: { hide: '.js-upload' },
                     list: '.js-files',
                     file: {
                         tpl: '.js-file-tpl',
                         preview: {
                             el: '.b-thumb__preview',
                             width: 40,
                             height: 40
                         },
                         upload: { hide: '.b-thumb__rotate' },
                         progress: '.progress .progress-bar',
                         complete: { }
                     }
                 },
                 onComplete: onComplete
             })
             .on('fileupload.fileapi filecomplete.fileapi', onUploadComplete)
             .on('hidden.bs.modal', function(evt) {
                 /* jshint unused: false */
                 /* clear file selection when modal is hidden (cancel button) */
                 hasErrors = false;
                 $(this).fileapi('widget').clear();
             });

         formData = null;
     }

     return setupModalFolderUpload;
 }));
