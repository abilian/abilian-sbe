(function() {
    'use strict';
function setupUpload(Abilian, $, FileAPI) {
    var form_data = {action: "upload"};
    form_data[Abilian.csrf_fieldname] = Abilian.csrf_token;

    function onUploadComplete(evt, ui) {
        var type = evt.type,
            uid = FileAPI.uid(ui.file),
            widget = $(this).fileapi('widget'),
            $file_ui = widget.$file(uid),
            $status_el = $file_ui.find('.statusicon'),
            $icon = $status_el.find('.glyphicon');

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
            data: form_data,
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
            onComplete: function (evt, ui) { location.reload(); }
        })
        .on('fileupload.fileapi filecomplete.fileapi', onUploadComplete)
        .on('hidden.bs.modal', function(evt) {
            /* clear file selection when modal is hidden (cancel button) */
            $(this).fileapi('widget').clear();
        });

    form_data = null;
};

 require(['Abilian', 'jquery', 'FileAPI', 'jquery.fileapi'], setupUpload);
})();
