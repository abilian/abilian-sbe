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

  // The message is tied to the field and said as it appears (its `aria-live`).
  function setError(message) {
    input.setAttribute("aria-invalid", message ? "true" : "false");
    if (!help) return;
    help.textContent = message || "";
    help.hidden = !message;
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
      .then((response) => {
        if (!response.ok) throw new Error(response.statusText);
        return response.json();
      })
      .then((data) => {
        if (data.valid) {
          setError(null);
          checked = true;
          submit.click();
        } else {
          setError(data.help_text);
        }
      })
      // A check that could not be made says so, rather than leave Save doing
      // nothing; the name is unique in its folder, and only this checks it.
      .catch(() => setError(input.dataset.checkFailed));
  });
}

document.querySelectorAll("[data-name-check-action]").forEach(setUp);
