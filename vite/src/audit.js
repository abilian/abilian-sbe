/* Show the chosen day: entries before the next local midnight, sent as UTC,
   which is how they are stored. */
const chooser = document.getElementById("date-chooser");
if (chooser) {
  chooser.addEventListener("change", () => {
    if (!chooser.value) return;

    const { form } = chooser;
    const [year, month, day] = chooser.value.split("-").map(Number);
    const nextMidnight = new Date(year, month - 1, day + 1);

    form.querySelector('input[name="after"]')?.remove();
    let before = form.querySelector('input[name="before"]');
    if (!before) {
      before = document.createElement("input");
      before.type = "hidden";
      before.name = "before";
      form.append(before);
    }
    before.value = nextMidnight.toISOString().slice(0, -1);
    form.submit();
  });
}
