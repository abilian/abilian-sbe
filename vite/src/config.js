// Settings from the server. abilian_base.html writes them as JSON because the
// Content Security Policy rules out an inline script.
export default JSON.parse(
  document.getElementById("abilian-config").textContent,
);
