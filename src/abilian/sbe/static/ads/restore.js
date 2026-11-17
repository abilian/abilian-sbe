/* What the reader chose last time, restored before first paint: the colour theme and a
 * folded sidebar.
 *
 * `ads/shell.html` loads this file twice, blocking (a plain <script src>, not `defer`): in
 * <head>, where it sets the theme on <html>, and as the first child of `.ads-app`, where it
 * folds or unfolds that element. Restored after first paint, the theme is a white flash on
 * every navigation for anyone who chose dark, and the fold is the page jumping sideways.
 *
 * A file rather than inline code, so that a strict Content-Security-Policy runs it:
 * `script-src 'self'` with no 'unsafe-inline' blocked the two inline scripts it replaces,
 * and the second sat outside any block, so an application could not swap it out. The
 * second load comes from the browser's cache. */
(function () {
  try {
    var here = document.currentScript && document.currentScript.parentNode;
    if (here && here.classList && here.classList.contains("ads-app")) {
      var folded = localStorage.getItem("ads-sidebar-folded");
      if (folded) here.classList.toggle("ads-app--folded", folded === "1");
    } else {
      var theme = localStorage.getItem("ads-theme");
      if (theme) document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) {
    // Storage refused (private mode, a blocked cookie policy): the defaults stand.
  }
})();
