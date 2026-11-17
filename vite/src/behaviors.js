// Small behaviours declared in the markup, for the pages that used to carry an
// inline handler for each of them.

/* <select data-autosubmit>: choosing a value posts the form. */
document.addEventListener("change", (event) => {
  if (event.target.matches("select[data-autosubmit]")) {
    event.target.form.submit();
  }
});

/* data-no-enter on a container: Enter in a text box does not submit the form. */
document.addEventListener("keydown", (event) => {
  if (
    event.key === "Enter" &&
    event.target.matches('input[type="text"], input[type="password"]') &&
    event.target.closest("[data-no-enter]")
  ) {
    event.preventDefault();
  }
});

/* A message's close button: shown here, since only here does it work. */
document.querySelectorAll("[data-dismiss][hidden]").forEach((button) => {
  button.hidden = false;
});

document.addEventListener("click", (event) => {
  const dismiss = event.target.closest("[data-dismiss]");
  if (dismiss) {
    dismiss.closest(".ads-alert").remove();
    return;
  }

  /* A button that opens a shared dialog tells its form where to post. */
  const opener = event.target.closest("[data-form-action]");
  if (opener) {
    const { formAction, formTarget } = opener.dataset;
    document.querySelectorAll(formTarget).forEach((form) => {
      form.action = formAction;
    });
  }
});
