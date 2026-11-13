import { confirmDialog } from "./confirm-dialog.js";

/* The attachment list's delete buttons stay disabled until this can ask first. */
const list = document.getElementById("attachments");
if (list) {
  const { deleteMessage, deleteLabel, cancelLabel } = list.dataset;

  list.querySelectorAll('li form > button[value="delete"]').forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();

      const message = document.createElement("div");
      const name = document.createElement("h2");
      const question = document.createElement("p");
      name.textContent = `"${button.closest("li").querySelector("a").textContent}"`;
      question.className = "text-xl font-light text-gray-600";
      question.textContent = deleteMessage;
      message.append(name, question);

      confirmDialog({
        message,
        okLabel: deleteLabel,
        cancelLabel,
        onConfirm() {
          const action = document.createElement("input");
          action.type = "hidden";
          action.name = "action";
          action.value = button.value;
          button.form.append(action);
          button.form.submit();
        },
      });
    });
    button.disabled = false;
  });
}
