/* Title-uniqueness check for the folder/document create and rename modals.
 *
 * A dialog opts in with data-name-check-action, and data-renames with the id of
 * the object it renames, if any.
 *
 * The first click is always cancelled, and the button re-clicked once the check
 * comes back clean: fetch() cannot decide inside the click handler. Re-clicking
 * rather than form.submit() keeps the button's name="action" value, which the
 * server handler reads.
 */

function setUp(modal) {
  const submit = modal.querySelector('button[type="submit"]');
  const input = modal.querySelector('input[name="title"]');
  const help = modal.querySelector("span.help-block");
  let checked = false;

  // The Tailwind classes are for the dialogs not yet on the design system.
  function setError(message) {
    input.setAttribute("aria-invalid", message ? "true" : "false");
    input.classList.toggle("border-red-500", Boolean(message));
    if (!help) return;
    help.textContent = message || "";
    help.hidden = !message;
    help.classList.toggle("hidden", !message);
    help.classList.toggle("text-red-600", Boolean(message));
  }

  submit.addEventListener("click", (event) => {
    if (checked) {
      checked = false;
      return; // Let the real submit through.
    }
    event.preventDefault();

    // Read now: one dialog renames whichever row it was opened from.
    const { nameCheckAction: action, renames = "" } = modal.dataset;
    const params = new URLSearchParams({
      object_id: renames,
      title: input.value,
      action,
    });

    fetch(`${input.dataset.checkUrl}?${params}`, { credentials: "same-origin" })
      .then((response) => response.json())
      .then((data) => {
        if (data.valid) {
          setError(null);
          checked = true;
          submit.click();
        } else {
          setError(data.help_text);
        }
      });
  });
}

document.querySelectorAll("[data-name-check-action]").forEach(setUp);
