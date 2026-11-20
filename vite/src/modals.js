/* Modals are native <dialog> elements.
 *
 * The platform supplies the backdrop, ESC-to-close, focus trapping, top-layer
 * stacking and inertness of the page behind. What it does not supply is a
 * declarative way to open one, so this is the whole of our modal code: one
 * delegated listener. Delegated, because the documents module injects rows
 * after load and they carry triggers too.
 *
 * This replaces a 311-line re-implementation of Bootstrap 3's modal, dropdown,
 * collapse, tab and alert plugins. Only the modal part of it was ever reached;
 * it drove visibility by writing `style.display`, which CSS then matched on.
 */

document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-modal-open]");
  // A link whose dialog is not on this page goes where it points.
  const dialog = opener && document.querySelector(opener.dataset.modalOpen);
  if (dialog) {
    event.preventDefault();
    // Opened from a menu, which has done its work: it closes, and its button
    // takes the focus, for the dialog to give it back to when it closes.
    const menu = opener.closest("details[open]");
    if (menu) {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
    dialog.showModal();
    // <dialog> has no "opened" event. Widgets that fill a modal from the page
    // it was opened over -- the document mover's folder listing -- need one.
    dialog.dispatchEvent(new Event("modal:open"));
    return;
  }

  if (event.target.closest("[data-modal-close]")) {
    event.preventDefault();
    event.target.closest("dialog").close();
    return;
  }

  // The dialog box fills the viewport and the visible panel is a child, so a
  // click that lands on the dialog itself landed outside the panel.
  if (event.target.matches("dialog")) {
    event.target.close();
  }
});
