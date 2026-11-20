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

  // Named by its title, or else by its message: a screen reader says what it asks.
  const dialog = document.createElement("dialog");
  dialog.className = "ads-modal__panel sbe-dialog";
  const id = `confirm-${Date.now()}`;
  dialog.setAttribute(
    "aria-labelledby",
    opts.title ? `${id}-title` : `${id}-message`,
  );
  if (opts.title) dialog.setAttribute("aria-describedby", `${id}-message`);

  const okClass = opts.danger ? "ads-btn--danger" : "ads-btn--primary";

  dialog.innerHTML = `
    <form method="dialog">
      ${
        opts.title
          ? `<div class="ads-modal__head">
               <h2 class="ads-modal__title" id="${id}-title">${opts.title}</h2>
             </div>`
          : ""
      }
      <div class="js-confirm-message ads-modal__body" id="${id}-message"></div>
      <div class="ads-modal__foot">
        <button value="cancel" class="ads-btn ads-btn--ghost">${opts.cancelLabel}</button>
        <button value="confirm" class="ads-btn ${okClass}">${opts.okLabel}</button>
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
