// Suggestions under the navbar search box.
//
// Replaces twitter typeahead 0.9 driven by Hogan -- 63KB of vendored jQuery
// plugins, and the reason 'unsafe-eval' had to stay in the Content Security
// Policy: Hogan compiles its templates by building functions out of strings.

import { attachCombobox, fetchJson } from "./combobox.js";
import config from "./config.js";

const api = config.api?.search;

function attach(input) {
  // [fqcn, "Friendly name"] pairs, empty until something has been indexed.
  const labels = new Map(api.object_types || []);

  attachCombobox(input, {
    container: input.closest("form"),
    search: (query, signal) =>
      fetchJson(`${api.live}?q=${encodeURIComponent(query)}`, signal),

    render(body, { addHeading, addOption }) {
      for (const [fqcn, hits] of Object.entries(body.results || {})) {
        if (!hits.length) continue;
        // Falls back to the class name, the way the server's friendly_fqcn
        // does, for a type that is indexed but not yet in the js api.
        addHeading(labels.get(fqcn) || fqcn.split(".").pop());
        for (const hit of hits) {
          addOption(hit.url, (node) => {
            node.textContent = hit.name;
          });
        }
      }
    },

    // With nothing highlighted, Enter falls through and submits the form, which
    // is the full search page.
    choose(url) {
      window.location = url;
    },
  });
}

// The mobile box never had suggestions: typeahead was wired to #search-box
// alone. Both are the same widget, so both get them.
if (api?.live) {
  document.querySelectorAll("#search-box, #search-box-mobile").forEach(attach);
}
