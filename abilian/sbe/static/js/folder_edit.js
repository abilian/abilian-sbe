define("SBEFolderEditSetup", ["Abilian", "jquery"], (Abilian, $) => {
  "use strict";
  function setupModalFolderInputnameCheck(modal, object_id, action) {
    const $submit = modal.find("button.btn-primary");
    const $input = modal.find('input[name="title"]');
    const checkUrl = $input.data("check-url");
    const $help_span = $input.next("span.help-block");
    const $control_group = $input.closest("div.form-group");

    $submit.on("click", (e) => {
      const title = $input.val();
      $.ajax(checkUrl, {
        async: false,
        cache: false,
        data: {
          object_id: object_id,
          title: title,
          action: action,
        },
        success(data) {
          const valid = data.valid;
          if (!valid) {
            e.preventDefault();
            $control_group.addClass("has-error");
            $help_span.text(data.help_text);
            $help_span.removeClass("hide");
          } else {
            $control_group.removeClass("has-error");
            $help_span.text("");
            $help_span.addClass("hide");
          }
        },
      });
    });
  }

  return setupModalFolderInputnameCheck;
});
