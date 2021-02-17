define("SBEFolderUploadSetup", [
  "Abilian",
  "jquery",
  "FileAPI",
  "jquery.fileapi",
], (Abilian, $, FileAPI) => {
  "use strict";
  function setupModalFolderUpload(modalId, url, messages) {
    let hasErrors = false;
    let formData = { action: "upload" };
    const errorMessages = {
      fileUploadError: "Error - File not uploaded",
      fileTooLargeError: "Error: maximum file size exceeded",
    };
    $.extend(errorMessages, messages || {});
    formData[Abilian.csrf_fieldname] = Abilian.csrf_token;

    function onComplete(evt, ui) {
      if (!hasErrors) {
        location.reload();
      }
    }

    function onUploadComplete(evt, ui) {
      const type = evt.type;
      const uid = FileAPI.uid(ui.file);
      const widget = $(this).fileapi("widget");
      const $fileUi = widget.$file(uid);
      const $statusEl = $fileUi.find(".statusicon");
      const $icon = $statusEl.find(".glyphicon");

      if (ui.error) {
        const progress = $fileUi.find(".progress");
        const errorEl = $('<span class="text-danger"></span>');
        let errorMsg = errorMessages.fileUploadError;
        hasErrors = true;
        $icon.removeClass("glyphicon-upload");
        $icon.addClass("glyphicon-warning-sign text-danger");

        switch (ui.status) {
          case 413: // Request Entity Too Large
            errorMsg = errorMessages.fileTooLargeError;
            break;
        }
        errorEl.text(errorMsg);
        progress.replaceWith(errorEl);
        return;
      }

      if (type === "fileupload") {
        $icon.addClass("glyphicon-upload");
        $statusEl.removeClass("hidden");
      } else if (type === "filecomplete") {
        $icon.removeClass("glyphicon-upload");
        $icon.addClass("glyphicon-ok");
        $statusEl.removeClass("btn-default");
        $statusEl.addClass("btn-success");
        $fileUi.find(".progress .progress-bar").width("100%");
      }
    }

    $("#" + modalId)
      .fileapi({
        multiple: true,
        url: url,
        data: formData,
        dataType: null, // not JSON
        clearOnComplete: false,
        elements: {
          ctrl: { upload: ".js-upload" },
          empty: { show: ".b-upload__hint" },
          emptyQueue: { hide: ".js-upload" },
          list: ".js-files",
          progress: '[data-fileapi="progress"]',
          file: {
            tpl: ".js-file-tpl",
            preview: {
              el: ".b-thumb__preview",
              width: 40,
              height: 40,
            },
            upload: { hide: ".b-thumb__rotate" },
            progress: '[data-fileapi="file.progress"]',
            complete: {},
          },
        },
        onComplete: onComplete,
      })
      .on("fileupload.fileapi filecomplete.fileapi", onUploadComplete)
      .on("hidden.bs.modal", function (evt) {
        /* clear file selection when modal is hidden (cancel button) */
        hasErrors = false;
        $(this).fileapi("widget").clear();
      });

    formData = null;
  }

  return setupModalFolderUpload;
});
