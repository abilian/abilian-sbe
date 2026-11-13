/* A delete button for urls managed by abilian.web.views.object.ObjectDelete. */

import config from "../config.js";
import { confirmDialog } from "../confirm-dialog.js";
import { registerWidget } from "./registry.js";

const DEFAULTS = {
  title: "La suppression est irréversible",
  message: "Do you really want to delete this entity ?",
  label: "Delete",
  cancelLabel: "Cancel",
};

function hiddenInput(name, value) {
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.value = value;
  return input;
}

// A link can only GET, and deleting takes a POST.
function postDelete(url) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = url;
  form.enctype = "multipart/form-data";
  form.append(
    hiddenInput(config.csrf_fieldname, config.csrf_token),
    hiddenInput("__action", "delete"),
  );
  document.body.append(form);
  form.submit();
}

registerWidget("deleteConfirm", (link, params) => {
  const options = { ...DEFAULTS, ...params };

  link.addEventListener("click", (event) => {
    event.preventDefault();
    confirmDialog({
      title: `<span class="text-red-600"><i class="fa fa-exclamation-triangle"></i> ${options.title}</span>`,
      message: `<p class="text-xl font-light text-gray-600">${options.message}</p>`,
      okLabel: options.label,
      cancelLabel: options.cancelLabel,
      onConfirm: () => postDelete(link.getAttribute("href")),
    });
  });
});
