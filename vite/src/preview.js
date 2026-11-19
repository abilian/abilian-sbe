// What the server makes of a field, shown as it is typed: what inviting does to each
// address (community/_invitees.html), a wiki page's text as the page will show it.
// The element marked `data-preview` holds the address that answers, and names its
// field in `data-preview-of`; the field's form is what is sent.

for (const pane of document.querySelectorAll("[data-preview]")) {
  const field = document.getElementById(pane.dataset.previewOf);
  let timer = null;
  let asked = "";

  const show = async () => {
    const text = field.value.trim();
    asked = text;
    if (!text) {
      pane.replaceChildren();
      return;
    }
    const response = await fetch(pane.dataset.preview, {
      method: "POST",
      body: new FormData(field.form),
    });
    // A later keystroke asked again meanwhile: its answer wins.
    if (asked !== text || !response.ok) return;
    pane.innerHTML = await response.text();
  };

  field.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(show, 300);
  });
  // A page being edited shows its text at once.
  show();
}
