/* The folder listing, in its table and gallery forms: selection, the actions on
 * each item, delete confirmation, and the move and change-owner dialogs.
 *
 * A document's page has a `folder-listing` form too, holding only that document,
 * so that the move dialog works from there the same way.
 */

import { confirmDialog } from "../confirm-dialog.js";

const listing = document.querySelector('form[name="folder-listing"]');

function selectedItems() {
  return [...listing.querySelectorAll('input[name="object-selected"]:checked')];
}

function copySelectionInto(container) {
  container.replaceChildren(
    ...selectedItems().map((item) => {
      const copy = item.cloneNode();
      copy.type = "hidden";
      copy.removeAttribute("id");
      return copy;
    }),
  );
}

/* What the selection's buttons apply to shows by itself (a CSS `:has()` on the
 * ticked boxes); this only ticks them all at once. */
function setUpSelection() {
  const checkboxes = () => listing.querySelectorAll('input[type="checkbox"]');

  listing.addEventListener("change", (event) => {
    if (!event.target.matches('input[type="checkbox"]')) return;
    if (event.target.matches(".doc-check-all")) {
      checkboxes().forEach((box) => {
        box.checked = event.target.checked;
      });
    }
  });
}

/* Each row carries hidden inputs named after its object: `title12`, `edit_url12`. */
function rowValue(prefix, objectId) {
  return document.getElementById(`${prefix}${objectId}`).value;
}

function setFormAction(selector, url) {
  document.querySelectorAll(selector).forEach((form) => {
    form.action = url;
  });
}

function setFieldValue(selector, value) {
  document.querySelectorAll(selector).forEach((field) => {
    field.value = value;
  });
}

/* Tick this one item alone, for the selection's buttons and dialogs to act on. */
function selectOnly(objectId) {
  listing.querySelectorAll('input[type="checkbox"]').forEach((box) => {
    box.checked = false;
  });
  document.getElementById(`check_${objectId}`).checked = true;
}

function clickSelectionButton(action) {
  listing.querySelector(`button[name="action"][value="${action}"]`).click();
}

function openRenameDialog(id, objectId) {
  const dialog = document.getElementById(id);
  // name-check.js leaves the object being renamed out of the uniqueness check.
  dialog.dataset.renames = objectId;
  dialog.showModal();
}

const ROW_ACTIONS = {
  "edit-document"({ objectId }) {
    setFormAction("#modal-edit-form", rowValue("edit_url", objectId));
    setFieldValue(".form-document-title", rowValue("title", objectId));
    setFieldValue(".form-document-description", rowValue("description", objectId));
    openRenameDialog("modal-edit", objectId);
  },
  "edit-folder"({ objectId }) {
    setFormAction("#modal-editfolder-form", rowValue("editfolder_url", objectId));
    setFieldValue(".form-folder-title", rowValue("title", objectId));
    setFieldValue(".form-folder-description", rowValue("description", objectId));
    openRenameDialog("modal-edit-folder", objectId);
  },
  "send-by-email"({ objectId }) {
    setFormAction("#modal-email-form", rowValue("email_url", objectId));
  },
  "replace-document"({ objectId }) {
    setFormAction("#modal-replace-form", rowValue("replace_url", objectId));
  },
  download({ objectId }) {
    selectOnly(objectId);
    clickSelectionButton("download");
  },
  move({ objectId }) {
    selectOnly(objectId);
  },
  delete({ objectId }) {
    selectOnly(objectId);
    clickSelectionButton("delete");
  },
};

function setUpRowActions() {
  // On the form, so as to run before the listener on the document that opens the
  // dialog: the move dialog copies the selection this sets.
  listing.addEventListener("click", (event) => {
    const button = event.target.closest("[data-row-action]");
    if (button) ROW_ACTIONS[button.dataset.rowAction](button.dataset);
  });
}

function setUpDeleteSelected() {
  const { deleteConfirm, deleteLabel, cancelLabel } = listing.dataset;

  listing.querySelectorAll('button[name="action"][value="delete"]').forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();

      const names = document.createElement("ul");
      names.className = "folder-items";
      for (const item of selectedItems()) {
        const name = document.createElement("li");
        name.textContent = item.dataset.title;
        names.append(name);
      }

      const message = document.createElement("div");
      message.append(deleteConfirm, names);

      confirmDialog({
        message,
        okLabel: deleteLabel,
        cancelLabel,
        onConfirm() {
          const action = document.createElement("input");
          action.type = "hidden";
          action.name = "action";
          action.value = button.value;
          button.form.append(action);
          button.form.submit();
        },
      });
    });
  });
}

/* Folders are titled by users: everything below is written with textContent. */
function setUpMoveDialog(modal) {
  const breadcrumbs = modal.querySelector(".breadcrumb");
  const folders = modal.querySelector("[data-folders]");
  const submit = document.getElementById("modal-move-button-submit");

  function folderLink({ title, url, id }) {
    const link = document.createElement("a");
    link.textContent = title;
    link.href = url;
    link.dataset.id = id;
    return link;
  }

  async function showFolder(url) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`${url} answered ${response.status}`);
    }
    const data = await response.json();

    breadcrumbs.replaceChildren(
      ...data.breadcrumbs.map((crumb) => {
        const item = document.createElement("li");
        item.append(folderLink(crumb));
        return item;
      }),
    );

    folders.replaceChildren(
      ...data.folders.map((folder) => {
        const item = document.createElement("li");
        item.append(folderLink(folder));
        return item;
      }),
    );

    const selectable = data.current_folder_selectable;
    submit.disabled = !selectable;
  }

  modal.querySelector("#modal-move-files-directory-listing").addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) return;
    event.preventDefault();
    modal.querySelector('input[name="target-folder"]').value = link.dataset.id;
    showFolder(link.href);
  });

  modal.addEventListener("modal:open", () => {
    const inputs = document.getElementById("modal-move-files-inputs");
    copySelectionInto(inputs);

    const target = document.createElement("input");
    target.type = "hidden";
    target.name = "target-folder";
    inputs.append(target);

    /* The dialog carries the folder to list. This used to be derived from
       document.location, which is only the right folder on a folder page --
       opening Move from a document asked for <document>/json and got a 404,
       so the dialog appeared with an empty listing. */
    showFolder(modal.dataset.listingUrl);
  });
}

function setUpChangeOwnerDialog(modal) {
  modal.addEventListener("modal:open", () => {
    copySelectionInto(modal.querySelector(".selected-items"));
  });
}

if (listing) {
  setUpSelection();
  setUpRowActions();
  setUpDeleteSelected();

  const moveDialog = document.getElementById("modal-move-files");
  if (moveDialog) setUpMoveDialog(moveDialog);

  const changeOwnerDialog = document.getElementById("modal-change-owner");
  if (changeOwnerDialog) setUpChangeOwnerDialog(changeOwnerDialog);

}
