// The members wizard's second page. The accounts travel to the last step as JSON
// in a hidden field; this keeps it in line with the tables.

function saySoIfEmpty(table) {
  if (!table.querySelector("tr[data-wizard-row]")) {
    table.querySelector("[data-wizard-empty]").hidden = false;
  }
}

/* Step 2: the accounts there are, and those to make. */
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
