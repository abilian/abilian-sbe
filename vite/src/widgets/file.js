/* File input widget: each file picked is uploaded straight away, and a hidden
 * input carries its handle when the form is posted. */

import config from "../config.js";
import { humanSize, upload } from "../upload.js";
import { registerWidget } from "./registry.js";

export class FileInput {
  constructor(node) {
    this.uploadsInProgress = 0;
    this.form = node.closest("form");
    this.button = node.querySelector(".js-file-button");
    this.listNode = node.querySelector(".selected-files");

    const input = this.button.querySelector("input");
    input.disabled = false;
    this.multiple = input.hasAttribute("multiple");
    input.removeAttribute("multiple");
    this.inputName = input.name;
    input.removeAttribute("name");

    if (node.dataset.cloned) {
      this.listNode.replaceChildren();
    } else {
      this.listNode
        .querySelectorAll(".file-item-existing")
        .forEach((item) => this.setupExistingFile(item));
      this.listNode
        .querySelectorAll(".file-item-uploaded")
        .forEach((item) => this.setupRemoveLink(item));
    }

    this.button.addEventListener("change", (event) => this.addFiles(event));
    this.form.addEventListener("submit", (event) => {
      if (this.uploadsInProgress > 0) {
        event.preventDefault();
        alert("Des fichiers sont en cours d'envoi"); // FIXME: i18n
      }
    });
  }

  addFiles(event) {
    let files = Array.from(event.target.files);
    // Clear it, so that picking the same file again still fires `change`.
    event.target.value = "";

    if (!this.multiple) {
      this.listNode.replaceChildren();
      files = files.slice(0, 1);
    }

    files.forEach((file) => {
      const item = this.createFileItem(file);
      this.setupRemoveLink(item);
      this.listNode.append(item);
      this.send(item, file);
    });
  }

  // Trash button on a file already saved: posts a marker to delete it.
  setupExistingFile(item) {
    const button = item.querySelector("button");
    if (!button) return;

    const marker = document.createElement("input");
    marker.type = "hidden";
    marker.name = button.dataset.name;
    marker.value = button.dataset.value;

    const mark = (deleting) => {
      button.classList.toggle("active", deleting);
      button.classList.toggle("btn-danger", deleting);
      button.classList.toggle("btn-default", !deleting);
      button.setAttribute("aria-pressed", String(deleting));
      if (deleting) item.append(marker);
      else marker.remove();
    };

    if (JSON.parse(button.dataset.deleted)) mark(true);
    button.addEventListener("click", () =>
      mark(!button.classList.contains("active")),
    );
  }

  setupRemoveLink(item) {
    item.querySelector("a")?.addEventListener("click", (event) => {
      event.preventDefault();
      item.remove();
    });
  }

  // Built as DOM, not as an HTML string: the name comes off the user's disk.
  createFileItem(file) {
    const item = document.createElement("div");
    item.className = "file-item";

    const info = document.createElement("span");
    info.className = "file-info";
    info.textContent = `${file.name.replace(/\\/g, "/").replace(/.*\//, "")} (${humanSize(file.size)})`;

    const remove = document.createElement("a");
    remove.className = "close";
    remove.href = "#";
    remove.textContent = "×";

    const progress = document.createElement("div");
    progress.className = "progress";
    progress.style.height = "0.2em";
    progress.innerHTML =
      '<div class="progress-bar" role="progressbar" aria-valuemin="0" ' +
      'aria-valuemax="100" aria-valuenow="0" style="width: 0"></div>';

    item.append(info, " ", remove, progress);
    return item;
  }

  send(item, file) {
    const body = new FormData();
    body.append("file", file);
    this.uploadsInProgress += 1;

    upload(config.api.upload.newFileUrl, body, {
      headers: {
        Accept: "application/json",
        "X-CSRF-Token": config.csrf_token,
      },
      onProgress: (fraction) => {
        item.querySelector(".progress-bar").style.width = `${fraction * 100}%`;
      },
    })
      .then((responseText) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = this.inputName;
        input.value = JSON.parse(responseText).handle;
        item.querySelector(".progress").remove();
        item.append(input);
      })
      .catch(() => {
        item.remove();
        alert("Echec de l'envoi du fichier!"); // FIXME: i18n
      })
      .finally(() => {
        this.uploadsInProgress -= 1;
      });
  }
}

registerWidget("fileInput", (node) => new FileInput(node));
