// A text input that suggests as you type: the ARIA combobox pattern, the
// keyboard, the debouncing, and dropping a request the user has typed past.
//
// Suggestions are user content, so callers fill them with DOM nodes and
// textContent; there is no HTML string in here for that to go wrong in.

const MIN_CHARS = 2;
const DEBOUNCE_MS = 180;

/**
 * @param {HTMLInputElement} input needs an id.
 * @param {object} callbacks
 * @param {HTMLElement} callbacks.container positioned; the list goes at its end.
 * @param {function(string, AbortSignal): Promise<*>} callbacks.search
 * @param {function(*, object)} callbacks.render receives what `search` resolved
 *   to, and `{addHeading(text), addOption(value, fill)}`.
 * @param {function(*)} callbacks.choose receives the `value` of the option.
 */
export function attachCombobox(input, { container, search, render, choose }) {
  const listbox = document.createElement("ul");
  listbox.className = "combobox-results";
  listbox.id = `${input.id}-results`;
  listbox.hidden = true;
  listbox.setAttribute("role", "listbox");
  container.append(listbox);

  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", listbox.id);
  input.setAttribute("aria-autocomplete", "list");

  let options = [];
  let active = -1;
  let timer = null;
  let inFlight = null;

  function close() {
    listbox.hidden = true;
    listbox.replaceChildren();
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    options = [];
    active = -1;
  }

  function highlight(index) {
    options.forEach(({ node }, i) => {
      node.classList.toggle("is-active", i === index);
      node.setAttribute("aria-selected", String(i === index));
    });
    active = index;
    if (index < 0) {
      input.removeAttribute("aria-activedescendant");
    } else {
      input.setAttribute("aria-activedescendant", options[index].node.id);
      options[index].node.scrollIntoView({ block: "nearest" });
    }
  }

  function pick({ value }) {
    close();
    choose(value);
  }

  const builders = {
    addHeading(text) {
      const heading = document.createElement("li");
      heading.className = "combobox-group";
      heading.setAttribute("role", "presentation");
      heading.textContent = text;
      listbox.append(heading);
    },
    addOption(value, fill) {
      const node = document.createElement("li");
      const option = { node, value };
      node.className = "combobox-hit";
      node.id = `${listbox.id}-${options.length}`;
      node.setAttribute("role", "option");
      node.setAttribute("aria-selected", "false");
      fill(node);
      // mousedown, not click: the input's blur would close the list first.
      node.addEventListener("mousedown", (event) => {
        event.preventDefault();
        pick(option);
      });
      listbox.append(node);
      options.push(option);
    },
  };

  async function lookUp(query) {
    inFlight?.abort();
    inFlight = new AbortController();
    let results;
    try {
      results = await search(query, inFlight.signal);
    } catch (error) {
      // An aborted request is the normal case: the user kept typing.
      if (error.name === "AbortError") return;
      close();
      throw error;
    }
    listbox.replaceChildren();
    options = [];
    render(results, builders);
    listbox.hidden = options.length === 0;
    input.setAttribute("aria-expanded", String(options.length > 0));
    highlight(-1);
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (query.length < MIN_CHARS) {
      inFlight?.abort();
      close();
      return;
    }
    timer = setTimeout(() => lookUp(query), DEBOUNCE_MS);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && options.length) {
      // Inside a dialog, Escape closes the list, not the dialog.
      event.preventDefault();
      close();
      return;
    }
    if (!options.length) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      highlight((active + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlight((active - 1 + options.length) % options.length);
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      pick(options[active]);
    }
  });

  input.addEventListener("blur", () => {
    clearTimeout(timer);
    inFlight?.abort();
    close();
  });
}

/** The JSON at `url`, or an Error that says which request failed. */
export async function fetchJson(url, signal) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`${url} answered ${response.status}`);
  }
  return response.json();
}
