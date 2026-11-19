/*
 * The folder page's upload dialog: build up a selection, send it one file at a
 * time, and reload once everything has arrived. A file that fails says why and
 * keeps the dialog open.
 */
import { humanSize, upload } from "../upload.js";

function setUp(dialog) {
  const form = dialog.querySelector("form");
  const picker = form.querySelector('input[type="file"]');
  const list = form.querySelector(".js-files");
  const rowTemplate = form.querySelector(".js-file-tpl");
  const sendButton = form.querySelector(".js-upload");
  const total = form.querySelector(".js-total-progress");
  const totalBar = total.querySelector("[role=progressbar]");

  let queue = [];
  let somethingArrived = false;
  let controller = null;

  function refreshSendButton() {
    sendButton.hidden = queue.length === 0;
  }

  function setBar(bar, fraction) {
    const percent = Math.round(fraction * 100);
    bar.style.width = `${fraction * 100}%`;
    // What the width shows, said to assistive technology too.
    bar.setAttribute("aria-valuenow", String(percent));
  }

  function showPreview(row, file) {
    if (!file.type.startsWith("image/")) {
      return;
    }
    const preview = row.querySelector(".js-file-preview");
    const url = URL.createObjectURL(file);
    preview.addEventListener("load", () => URL.revokeObjectURL(url));
    preview.src = url;
    preview.hidden = false;
  }

  function addFile(file) {
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector("li");
    const entry = { file, row };

    row.querySelector(".js-file-name").textContent = file.name;
    row.querySelector(".js-file-size").textContent =
      `(${humanSize(file.size)})`;
    showPreview(row, file);
    row.querySelector(".js-file-remove").addEventListener("click", () => {
      queue = queue.filter((queued) => queued !== entry);
      row.remove();
      refreshSendButton();
    });

    queue.push(entry);
    list.append(fragment);
  }

  function errorMessage(status) {
    return status === 413
      ? dialog.dataset.errorTooLarge
      : dialog.dataset.errorUpload;
  }

  async function sendFile({ file, row }, onProgress, signal) {
    const body = new FormData(form);
    body.set("action", "upload");
    body.set("file", file);

    const bar = row.querySelector("[role=progressbar]");
    row.querySelector(".js-file-remove").hidden = true;
    row.querySelector(".js-file-progress").hidden = false;

    try {
      await upload(form.getAttribute("action"), body, {
        signal,
        onProgress: (fraction) => {
          setBar(bar, fraction);
          onProgress(fraction);
        },
      });
    } catch (err) {
      const error = row.querySelector(".js-file-error");
      error.textContent = errorMessage(err.status);
      error.hidden = false;
      row.querySelector(".js-file-progress").hidden = true;
      row.querySelector(".js-file-failed").hidden = false;
      return false;
    }

    row.querySelector(".js-file-progress").hidden = true;
    row.querySelector(".js-file-sent").hidden = false;
    return true;
  }

  async function send() {
    const entries = queue;
    const { signal } = (controller = new AbortController());
    let allArrived = true;

    queue = [];
    refreshSendButton();
    picker.disabled = true;
    total.hidden = false;

    for (const [index, entry] of entries.entries()) {
      if (signal.aborted) {
        return;
      }
      const arrived = await sendFile(
        entry,
        (fraction) => setBar(totalBar, (index + fraction) / entries.length),
        signal,
      );
      somethingArrived ||= arrived;
      allArrived &&= arrived;
    }

    picker.disabled = false;
    total.hidden = true;
    if (allArrived) {
      location.reload();
    }
  }

  function clear() {
    queue = [];
    list.replaceChildren();
    picker.disabled = false;
    total.hidden = true;
    setBar(totalBar, 0);
    refreshSendButton();
  }

  picker.addEventListener("change", () => {
    Array.from(picker.files).forEach(addFile);
    // Clear it, so that picking the same file again still fires `change`.
    picker.value = "";
    refreshSendButton();
  });

  sendButton.addEventListener("click", send);

  // However the dialog was closed (Cancel, Escape, the backdrop).
  dialog.addEventListener("close", () => {
    controller?.abort();
    // The listing behind the dialog is out of date.
    if (somethingArrived) {
      location.reload();
      return;
    }
    clear();
  });
}

// Only folder pages have the dialog.
const dialog = document.getElementById("modal-upload-files");
if (dialog) setUp(dialog);
