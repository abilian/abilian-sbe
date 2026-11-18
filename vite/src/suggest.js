// The bar's search: as one types, the server's suggestions open under the field
// (search/_suggestions.html), and on an empty field what one searched and opened
// lately; the arrows move among them, Enter opens the current one, Escape closes
// them; `/` reaches the field from any page. On a phone, the bar's magnifier opens
// the field over the bar.

const box = document.querySelector("[data-suggest]");
if (box) {
  const form = box.querySelector("form");
  const input = form.querySelector('input[name="q"]');
  let timer = null;
  let asked = "";

  const panel = () => box.querySelector("#suggestions");
  const options = () => [...box.querySelectorAll('[role="option"]')];
  const current = () =>
    box.querySelector('[role="option"][aria-selected="true"]');

  const close = () => {
    asked = "";
    panel()?.remove();
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    box.classList.remove("is-open");
  };

  const choose = (option) => {
    options().forEach((o) =>
      o.setAttribute("aria-selected", String(o === option)),
    );
    if (!option) return;
    input.setAttribute("aria-activedescendant", option.id);
    option.scrollIntoView({ block: "nearest" });
  };

  const suggest = async () => {
    const q = input.value.trim();
    // One letter matches too much to say anything.
    if (q.length === 1) {
      close();
      return;
    }
    const params = new URLSearchParams({ q });
    const scope = form.querySelector('input[name="community"]');
    if (scope?.checked) params.set("community", scope.value);
    const query = params.toString();
    asked = query;
    const response = await fetch(`${box.dataset.suggest}?${query}`, {
      headers: { Accept: "text/html" },
    });
    const html = response.ok ? (await response.text()).trim() : "";
    // A later keystroke asked again meanwhile: its answer wins.
    if (asked !== query) return;
    // Nothing to suggest: an empty field with nothing searched or opened yet.
    if (!html) {
      close();
      return;
    }
    panel()?.remove();
    box.insertAdjacentHTML("beforeend", html);
    input.setAttribute("aria-expanded", "true");
    box.classList.add("is-open");
    choose(options()[0]);
  };

  input.addEventListener("focus", () => {
    if (!input.value.trim() && !panel()) suggest();
  });

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(suggest, 150);
  });

  input.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    const all = options();
    const at = all.indexOf(current());
    if (event.key === "ArrowDown" && all.length) {
      event.preventDefault();
      choose(all[(at + 1) % all.length]);
    } else if (event.key === "ArrowUp" && all.length) {
      event.preventDefault();
      choose(all[(at - 1 + all.length) % all.length]);
    } else if (event.key === "Enter" && current()) {
      event.preventDefault();
      window.location.assign(current().href);
    } else if (event.key === "Escape" && panel()) {
      // Closes the suggestions and keeps the text: a search field's Escape would
      // empty it. A second Escape, with nothing open, still does.
      event.preventDefault();
      close();
    }
  });

  // A click elsewhere closes them; the magnifier's own click opens the field.
  document.addEventListener("click", (event) => {
    if (box.contains(event.target) || event.target.closest(".sbe-bar-search"))
      return;
    close();
  });
  document
    .querySelector(".sbe-bar-search")
    ?.addEventListener("click", (event) => {
      event.preventDefault();
      box.classList.add("is-open");
      input.focus();
    });

  // `/` from anywhere but a field being typed in.
  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.defaultPrevented) return;
    if (event.target.closest("input, textarea, select, [contenteditable]"))
      return;
    event.preventDefault();
    input.focus();
  });
}
