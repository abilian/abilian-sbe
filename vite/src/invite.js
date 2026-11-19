// Inviting people: as addresses are typed, the server says what will happen to
// each (community/_invitees.html), under the field.

const preview = document.querySelector("[data-invitees]");
if (preview) {
  const field = document.getElementById("wizard-emails");
  let timer = null;
  let asked = "";

  const show = async () => {
    const emails = field.value.trim();
    asked = emails;
    if (!emails) {
      preview.replaceChildren();
      return;
    }
    const response = await fetch(preview.dataset.invitees, {
      method: "POST",
      body: new FormData(field.form),
    });
    // A later keystroke asked again meanwhile: its answer wins.
    if (asked !== emails || !response.ok) return;
    preview.innerHTML = await response.text();
  };

  field.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(show, 300);
  });
}
