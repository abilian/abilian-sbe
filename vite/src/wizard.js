// The members wizard's second and third pages. The accounts travel between the
// steps as JSON in a hidden field; these keep it in line with the table.

function saySoIfEmpty(table) {
  if (!table.querySelector("tr[data-wizard-row]")) {
    table.querySelector("[data-wizard-empty]").hidden = false;
  }
}

/* Step 2: existing accounts. */
const emailsField = document.querySelector("[data-wizard-accounts]");
if (emailsField) {
  const readAccounts = () => JSON.parse(emailsField.value);
  const writeAccounts = (accounts) => {
    emailsField.value = JSON.stringify(accounts);
  };

  document.addEventListener("change", (event) => {
    if (!event.target.matches("[data-wizard-role]")) return;
    const { wizardRole: email } = event.target.dataset;
    writeAccounts(
      readAccounts().map((account) =>
        account.email === email
          ? { ...account, role: event.target.value }
          : account,
      ),
    );
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-wizard-remove]");
    if (!button) return;
    const table = button.closest("table");
    const { wizardRemove: email } = button.dataset;
    button.closest("tr").remove();
    writeAccounts(readAccounts().filter((account) => account.email !== email));
    saySoIfEmpty(table);
  });
}

/* Step 3: new accounts. The table is the state; the field is filled on saving. */
const saveButton = document.querySelector("[data-wizard-save]");
if (saveButton) {
  const table = document.querySelector("[data-wizard-new-accounts]");

  table.addEventListener("click", (event) => {
    const button = event.target.closest("[data-wizard-remove]");
    if (!button) return;
    button.closest("tr").remove();
    saySoIfEmpty(table);
  });

  saveButton.addEventListener("click", () => {
    let missing = 0;
    table.querySelectorAll(".wizard-required").forEach((input) => {
      const empty = input.value.trim() === "";
      input.classList.toggle("border-2", empty);
      input.classList.toggle("border-red-400", empty);
      if (empty) missing += 1;
    });
    document.querySelector(".wizard-warning").hidden = missing === 0;
    if (missing) return;

    const value = (row, name) => row.querySelector(`[name="${name}"]`).value;
    const accounts = [...table.querySelectorAll("tr[data-wizard-row]")].map(
      (row) => ({
        email: value(row, "account"),
        first_name: value(row, "first_name"),
        last_name: value(row, "last_name"),
        role: value(row, "role"),
      }),
    );

    document.getElementById("new_accounts").value = JSON.stringify(accounts);
    document.getElementById("wizard-form").submit();
  });
}
