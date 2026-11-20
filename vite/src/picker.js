// Choosing a user by name, for forms that post a user id.
//
//   <input type="text" name="user" data-picker="{{ url }}" required>
//
// `url` answers `?q=` with {results: [{id, text, name?, email?, role?}]}. The
// input becomes the hidden field that is posted, and a visible text box takes
// its place, id included, so that labels keep pointing at what you type in.
//
// data-picker-value and data-picker-label give a choice already made, and
// data-picker-submit posts the form as soon as the choice changes.

import { attachCombobox, fetchJson } from "./combobox.js";

function renderHit(node, hit) {
  const name = document.createElement("strong");
  name.textContent = hit.name || hit.text;
  node.append(name);

  if (hit.role) {
    const role = document.createElement("small");
    role.className = "picker-role";
    role.textContent = hit.role;
    node.append(" ", role);
  }
  if (hit.email) {
    const email = document.createElement("div");
    email.className = "picker-email";
    email.textContent = hit.email;
    node.append(email);
  }
}

function attach(field) {
  const box = document.createElement("input");
  box.type = "text";
  box.id = field.id;
  box.className = field.className;
  box.placeholder = field.placeholder;
  // What names and explains the field goes with it to the box one types in.
  for (const name of ["aria-label", "aria-describedby"]) {
    if (field.hasAttribute(name))
      box.setAttribute(name, field.getAttribute(name));
  }
  box.required = field.required;
  box.autocomplete = "off";
  box.value = field.dataset.pickerLabel || "";

  const wrapper = document.createElement("span");
  wrapper.className = "picker";
  field.after(wrapper);
  wrapper.append(box);

  field.removeAttribute("id");
  field.type = "hidden";
  field.value = field.dataset.pickerValue || "";

  const submitOnChange = "pickerSubmit" in field.dataset;

  function setChoice(value, label) {
    const changed = field.value !== value;
    field.value = value;
    box.value = label;
    if (submitOnChange && changed) field.form.submit();
  }

  attachCombobox(box, {
    container: wrapper,
    search(query, signal) {
      const url = new URL(field.dataset.picker, window.location.href);
      url.searchParams.set("q", query);
      return fetchJson(url, signal);
    },
    render({ results }, { addOption }) {
      for (const hit of results) {
        addOption(hit, (node) => renderHit(node, hit));
      }
    },
    choose: (hit) => setChoice(String(hit.id), hit.text),
  });

  // Whatever was chosen is no longer what the box says. On a `submit` picker
  // this waits for blur, or every keystroke would post the form.
  box.addEventListener("input", () => {
    if (!submitOnChange) field.value = "";
  });

  // Text that was never turned into a choice must not look like one.
  box.addEventListener("blur", () => {
    if (submitOnChange) {
      if (box.value.trim() === "") setChoice("", "");
      else box.value = field.dataset.pickerLabel || "";
    } else if (!field.value) {
      box.value = "";
    }
  });

  // Enter with nothing chosen would post an empty field.
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !field.value) event.preventDefault();
  });
}

document.querySelectorAll("input[data-picker]").forEach(attach);
