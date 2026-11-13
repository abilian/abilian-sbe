/* The folder listing, in its table and gallery forms: selection, the actions on
 * each row, delete confirmation, and the move and change-owner dialogs.
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

function setUpSelection() {
  const checkboxes = () => listing.querySelectorAll('input[type="checkbox"]');
  const menu = document.getElementById("horizontal-doc-menu");

  function setSelected(checked) {
    listing.querySelectorAll('input[name="object-selected"]').forEach((box) => {
      box.checked = checked;
    });
  }

  listing.querySelector("a[href='#select-all']")?.addEventListener("click", (e) => {
    e.preventDefault();
    setSelected(true);
  });
  listing.querySelector("a[href='#unselect-all']")?.addEventListener("click", (e) => {
    e.preventDefault();
    setSelected(false);
  });

  listing.addEventListener("change", (event) => {
    if (!event.target.matches('input[type="checkbox"]')) return;
    if (event.target.matches(".doc-check-all")) {
      checkboxes().forEach((box) => {
        box.checked = event.target.checked;
      });
    }
    if (menu) {
      const anyChecked = [...checkboxes()].some((box) => box.checked);
      menu.style.display = anyChecked ? "" : "none";
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

function setText(selector, text) {
  document.querySelector(selector).textContent = text;
}

const ROW_ACTIONS = {
  "edit-document"({ objectId }) {
    setFormAction("#modal-edit-form", rowValue("edit_url", objectId));
    setFieldValue(".form-document-title", rowValue("title", objectId));
    setFieldValue(".form-document-description", rowValue("description", objectId));
    document.getElementById("modal-edit").showModal();
  },
  "edit-folder"({ objectId }) {
    setFormAction("#modal-editfolder-form", rowValue("editfolder_url", objectId));
    setFieldValue(".form-folder-title", rowValue("title", objectId));
    setFieldValue(".form-folder-description", rowValue("description", objectId));
    document.getElementById("modal-edit-folder").showModal();
  },
  "send-by-email"({ objectId }) {
    setFormAction("#modal-email-form", rowValue("email_url", objectId));
  },
  "replace-document"({ objectId }) {
    setFormAction(".modal-replacedoc-form", rowValue("replace_url", objectId));
  },
  "delete-document"({ objectId }) {
    setFormAction("#modal-delete-document", rowValue("delete_url", objectId));
    setText("#delete-doc-title", rowValue("title", objectId));
  },
  "delete-folder"({ folderUrl, folderTitle }) {
    setFormAction("#modal-delete-folders", folderUrl);
    setText("#delete-folder-title", folderTitle);
  },
  "download-folder"({ folderUrl }) {
    setFormAction("#folder_content_download", folderUrl);
    document.getElementById("document-folder-download").click();
  },
  "move"({ objectId }) {
    listing.querySelectorAll('input[type="checkbox"]').forEach((box) => {
      box.checked = false;
    });
    document.getElementById(`check_${objectId}`).checked = true;
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

  listing.querySelectorAll('button.btn-danger[value="delete"]').forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();

      const names = document.createElement("ul");
      names.className = "folder-items";
      for (const item of selectedItems()) {
        const titleCell = item.closest("td")?.nextElementSibling;
        if (titleCell) {
          const name = document.createElement("li");
          name.textContent = titleCell.textContent.trim();
          names.append(name);
        }
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
  const tbody = modal.querySelector("tbody");
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

    tbody.replaceChildren(
      ...data.folders.map((folder) => {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        const divider = document.createElement("span");
        divider.className = "divider";
        divider.textContent = "/";
        cell.append(folderLink(folder), divider);
        row.append(cell);
        return row;
      }),
    );

    const selectable = data.current_folder_selectable;
    submit.disabled = !selectable;
    submit.classList.toggle("disabled", !selectable);
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

function setUpGalleryFilter(filter) {
  filter.addEventListener("input", () => {
    const wanted = filter.value.toLowerCase();
    document.querySelectorAll(".gallery_element").forEach((element) => {
      const name = element
        .querySelector(".document-gallery-infos p:nth-child(1)")
        .textContent.toLowerCase()
        .split(".")[0];
      element.style.display = name.includes(wanted) ? "" : "none";
    });
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

  const galleryFilter = document.getElementById("filter");
  if (galleryFilter) setUpGalleryFilter(galleryFilter);
}
