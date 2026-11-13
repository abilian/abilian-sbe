/* Confirmation dialogs, on a native <dialog>.
 *
 * Replaces bootbox, which drives Bootstrap's jQuery modal plugin. That plugin
 * went with Bootstrap's JavaScript, so every bootbox call threw
 * "$.fn.modal is not defined" and every destructive action -- delete a
 * document, a folder, a wiki attachment, an entity -- silently did nothing.
 *
 * `message` is a DOM node, or a string inserted as HTML: never build the string
 * from what a user typed, such as the name of a document.
 */

const DEFAULTS = {
  title: "",
  message: "",
  okLabel: "OK",
  cancelLabel: "Cancel",
  danger: true,
};

export function confirmDialog(options) {
  const opts = { ...DEFAULTS, ...options };

  const dialog = document.createElement("dialog");
  // m-auto matters: a native <dialog> is centred by the UA stylesheet's
  // `margin: auto`, and Tailwind's preflight resets margin to 0, which pins
  // the dialog to the top-left corner.
  dialog.className =
    "m-auto rounded-lg border border-gray-200 p-0 shadow-2xl " +
    "backdrop:bg-black/50 w-full max-w-lg";

  const okClasses = opts.danger
    ? "bg-red-600 hover:bg-red-700"
    : "bg-blue-600 hover:bg-blue-700";

  dialog.innerHTML = `
    <form method="dialog">
      ${
        opts.title
          ? `<div class="flex items-center justify-between border-b border-gray-200 p-4">
               <h3 class="text-lg font-semibold text-gray-900">${opts.title}</h3>
             </div>`
          : ""
      }
      <div class="js-confirm-message p-4 text-gray-700"></div>
      <div class="flex items-center justify-end gap-2 border-t border-gray-200 p-4">
        <button value="cancel"
                class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm
                       font-medium text-gray-700 hover:bg-gray-50">
          ${opts.cancelLabel}
        </button>
        <button value="confirm"
                class="rounded-md px-4 py-2 text-sm font-medium text-white ${okClasses}">
          ${opts.okLabel}
        </button>
      </div>
    </form>
  `;

  const body = dialog.querySelector(".js-confirm-message");
  if (typeof opts.message === "string") {
    body.innerHTML = opts.message;
  } else {
    body.append(opts.message);
  }

  document.body.appendChild(dialog);
  dialog.addEventListener("close", () => {
    const confirmed = dialog.returnValue === "confirm";
    dialog.remove();
    if (confirmed && opts.onConfirm) opts.onConfirm();
  });

  dialog.showModal();
  return dialog;
}
