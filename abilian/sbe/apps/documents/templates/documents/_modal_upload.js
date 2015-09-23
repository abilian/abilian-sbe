(function(factory) {
    'use strict';
    require(['Abilian', 'jquery', 'FileAPI', 'jquery.fileapi'], factory);
}
 (function setupUpload(Abilian, $, FileAPI) {
     'use strict';
     var formData = {action: 'upload'};
     formData[Abilian.csrf_fieldname] = Abilian.csrf_token;

     var hasErrors = false;

     function onComplete(evt, ui) {
         if (!hasErrors) {
             location.reload();
         }
     }

    function onUploadComplete(evt, ui) {
        var type = evt.type,
            uid = FileAPI.uid(ui.file),
            widget = $(this).fileapi('widget'),
            $file_ui = widget.$file(uid),
            $status_el = $file_ui.find('.statusicon'),
            $icon = $status_el.find('.glyphicon');

        if (ui.error) {
            var progress = $file_ui.find('.progress'),
                errorEl = $('<span class="text-danger"></span>'),
                errorMsg = {{ _('Error - File not uploaded')|tojson }};
            hasErrors = true;
            $icon.removeClass('glyphicon-upload');
            $icon.addClass('glyphicon-warning-sign text-danger');

            switch (ui.status) {
            case 413: //Request Entity Too Large
                errorMsg = {{ _('Error: maximum file size exceeded')|tojson }};
                break;
            }
            errorEl.text(errorMsg);
            progress.replaceWith(errorEl);
            return;
        }

        if (type == 'fileupload') {
            $icon.addClass('glyphicon-upload');
            $status_el.removeClass('hidden');
        }
        else if (type == 'filecomplete') {
            $icon.removeClass('glyphicon-upload');
            $icon.addClass('glyphicon-ok');
            $status_el.removeClass('btn-default');
            $status_el.addClass('btn-success');
            $file_ui.find('.progress .progress-bar').width('100%');
        }
    }

    $('#modal-upload-files')
        .fileapi({
            multiple: true,
            url: {{ folder_post_url|tojson }},
            data: formData,
            dataType: null, {# not JSON #}
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
            /* clear file selection when modal is hidden (cancel button) */
            hasErrors = false;
            $(this).fileapi('widget').clear();
        });

    formData = null;
}));
