/* The viewers panel on a thread: posters in the strip, or everyone below it. */
const viewersToggle = document.querySelector("[data-viewers-toggle]");
if (viewersToggle) {
  const posters = document.querySelector(".viewers-panel-posters");
  const content = document.querySelector(".viewers-panel-content");
  const icon = viewersToggle.querySelector(".fa");
  let open = false;

  viewersToggle.addEventListener("click", () => {
    open = !open;
    if (posters) posters.style.display = open ? "none" : "";
    content.style.display = open ? "block" : "";
    icon.className = `fa fa-chevron-${open ? "up" : "down"}`;
  });
}

/* Characters left in a new thread's title. */
const titleInput = document.querySelector("[data-title-counter] #title");
if (titleInput) {
  const max = Number(titleInput.closest("[data-title-counter]").dataset.titleCounter);
  const counter = document.createElement("span");
  titleInput.parentNode.append(counter);

  const update = () => {
    const length = titleInput.value.length;
    counter.textContent = `${length}/${max}`;
    counter.className =
      "thread-title-counter text-sm ml-2 px-2 py-0.5 rounded " +
      (length > max ? "bg-orange-500 text-white" : "bg-gray-100 text-gray-600");
  };

  titleInput.addEventListener("input", update);
  update();
}
