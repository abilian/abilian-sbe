/* Turning the pages of a document's preview (documents/document.html): the
 * toolbar's buttons, and the arrow keys while the pointer is over the page. */

function setupDocumentViewer() {
  const container = document.querySelector("[data-preview-pages]");
  if (!container) return;

  const img = container.querySelector("img");
  const steps = document.querySelectorAll("[data-preview-step]");
  const label = document.querySelector("[data-preview-page]");
  const pageNum = Number(container.dataset.previewPages);
  if (!img || pageNum < 2) return;

  const imgSrc = img.getAttribute("src");
  let page = 0;

  function turn(step) {
    page = Math.min(Math.max(page + step, 0), pageNum - 1);
    img.setAttribute("src", `${imgSrc}&page=${page}`);
    if (label) label.textContent = String(page + 1);
    steps.forEach((button) => {
      const towards = page + Number(button.dataset.previewStep);
      button.disabled = towards < 0 || towards >= pageNum;
    });
  }

  function keyDown(event) {
    const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    if (!step) return;
    event.preventDefault();
    turn(step);
  }

  steps.forEach((button) => {
    button.addEventListener("click", () =>
      turn(Number(button.dataset.previewStep)),
    );
  });

  // Only while the pointer is over the page, so as not to take the arrows from
  // the rest of the page.
  container.addEventListener("mouseenter", () => {
    document.addEventListener("keydown", keyDown);
  });
  container.addEventListener("mouseleave", () => {
    document.removeEventListener("keydown", keyDown);
  });
}

setupDocumentViewer();
