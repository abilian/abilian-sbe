/* A table of repeated form fields, with a button to add a row and one on each
 * row to remove it. Each new row is a blank copy of the first. */

import { initWidget, registerWidget } from "./registry.js";

function iconButton(icon, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", label);
  button.innerHTML = `<i class="fa fa-${icon}" aria-hidden="true"></i>`;
  return button;
}

function blankCopyOf(row) {
  const copy = row.cloneNode(true);
  copy.querySelectorAll("input").forEach((input) => {
    if (
      !["checkbox", "radio"].includes(input.type) &&
      input.dataset.shortName !== "csrf_token"
    ) {
      input.setAttribute("value", "");
    }
  });
  copy.querySelectorAll("textarea").forEach((textarea) => {
    textarea.textContent = "";
  });
  return copy;
}

function setUp(table, placement = "top") {
  const prefix = table.dataset.prefix;
  const tbody = table.tBodies[0];
  const rowsOf = () => [...tbody.rows];

  let nextIndex = rowsOf().length;
  // Before the row grows its remove button: addRow gives each copy its own.
  const template = rowsOf()[0] && blankCopyOf(rowsOf()[0]);

  function appendRemoveCell(row) {
    const cell = document.createElement("td");
    cell.append(iconButton("times", "Remove"));
    cell.firstChild.addEventListener("click", () => row.remove());
    row.append(cell);
  }

  function addRow() {
    const row = template.cloneNode(true);

    row.querySelectorAll("input").forEach((input) => {
      const { shortName } = input.dataset;
      const base = `${prefix}-${nextIndex}`;
      input.name = shortName ? `${base}-${shortName}` : base;
      input.id = input.name;
    });
    row.querySelectorAll("select").forEach((select) => {
      const name = select.id
        .split("-")
        .map((part) => (Number.isNaN(Number(part)) ? part : nextIndex))
        .join("-");
      select.name = name;
      select.id = name;
    });

    appendRemoveCell(row);
    tbody.append(row);
    row.querySelectorAll(".js-widget").forEach((widget) => {
      widget.dataset.cloned = "true";
      initWidget(widget);
    });
    nextIndex += 1;
  }

  function appendAddCell(headerRow) {
    if (!headerRow) return;
    const cell = document.createElement("th");
    cell.style.width = "1em";
    cell.append(iconButton("plus", "Add"));
    cell.firstChild.addEventListener("click", addRow);
    headerRow.append(cell);
  }

  table.classList.add("dynamic-row-widget");
  if (placement.includes("top")) appendAddCell(table.tHead?.rows[0]);
  if (placement.includes("bottom")) appendAddCell(table.tFoot?.rows[0]);
  rowsOf().forEach(appendRemoveCell);
}

registerWidget("dynamicRowWidget", setUp);
