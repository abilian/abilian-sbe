/* Page-flip navigation for the document preview (documents/document.html). */

const KEY_LEFT = 37;
const KEY_RIGHT = 39;

function setupDocumentViewer() {
  const container = document.querySelector(".preview-container");
  if (!container) return;

  const img = container.querySelector("img.preview");
  const previewPrev = container.querySelector(".preview-prev");
  const previewNext = container.querySelector(".preview-next");
  if (!img) return;

  const imgSrc = img.getAttribute("src");
  const pageNum = Number(container.dataset.pageNum);

  function showPage(page) {
    img.setAttribute("src", `${imgSrc}&page=${page}`);
    img.dataset.page = String(page);
  }

  // TODO: what if we want to go past the last page?
  function loadNext() {
    const page = Number(img.dataset.page) + 1;
    showPage(page >= pageNum ? page - 1 : page);
  }

  function loadPrev() {
    const page = Number(img.dataset.page) - 1;
    showPage(page < 0 ? 0 : page);
  }

  function keyDown(e) {
    if (e.keyCode === KEY_RIGHT) {
      e.preventDefault();
      loadNext();
    } else if (e.keyCode === KEY_LEFT) {
      e.preventDefault();
      loadPrev();
    }
  }

  if (previewNext) previewNext.addEventListener("click", loadNext);
  if (previewPrev) previewPrev.addEventListener("click", loadPrev);

  // Arrow keys only while the pointer is over the preview, so they do not
  // hijack the arrows for the rest of the page.
  if (pageNum > 1) {
    container.addEventListener("mouseenter", () => {
      document.addEventListener("keydown", keyDown);
    });
    container.addEventListener("mouseleave", () => {
      document.removeEventListener("keydown", keyDown);
    });
  } else {
    if (previewPrev) previewPrev.style.display = "none";
    if (previewNext) previewNext.style.display = "none";
  }
}

setupDocumentViewer();
