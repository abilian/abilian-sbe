/* The behaviour `ads/shell.html` and a few components need. Vendored by `abilian-ds sync`.
 *
 * Five things, none of which a component can do with CSS alone: a dropdown that closes when
 * you click away, a drawer that opens and traps nothing, the theme toggle, a sidebar that
 * remembers which groups you left open, and the menu button that folds it or opens it. `.ads-dropdown` and `.ads-drawer` are not usable
 * without this, which is why it ships rather than being left as an exercise.
 *
 * No framework, no build step, no globals but the two functions the drawer needs. Everything
 * is delegated from `document`, so an element rendered later — by a server region swap, say —
 * works without being registered.
 */
(function () {
  "use strict";

  var MENUS =
    "details.ads-dropdown[open], .ads-app--horizontal .ads-nav__group details[open]";

  function closeMenus(except) {
    document.querySelectorAll(MENUS).forEach(function (menu) {
      if (!except || !menu.contains(except)) menu.open = false;
    });
  }

  function toggleDrawer(id, on) {
    var panel = document.getElementById(id);
    if (!panel) return;
    panel.classList.toggle("is-open", on);
    var backdrop = document.querySelector('[data-drawer-for="' + id + '"]');
    if (backdrop) backdrop.classList.toggle("is-open", on);
    // the drawer is off-screen and `visibility: hidden` when closed, so focus has to be moved
    // in deliberately — otherwise the first Tab lands on something behind the panel
    if (on) {
      var first = panel.querySelector("button, [href], input, select, textarea");
      if (first) first.focus();
    }
  }

  function closeDrawers() {
    document.querySelectorAll(".ads-drawer.is-open").forEach(function (panel) {
      toggleDrawer(panel.id, false);
    });
  }

  // `localStorage` throws in a private window and with site data blocked. A page that does not
  // remember is a much smaller problem than one that does not render, so every access is
  // guarded and the default simply stands.
  function remember(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      /* private mode */
    }
  }

  function recall(key) {
    try {
      return localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  document.addEventListener("click", function (event) {
    closeMenus(event.target);

    var opener = event.target.closest("[data-drawer]");
    if (opener) {
      closeDrawers();
      toggleDrawer(opener.getAttribute("data-drawer"), true);
    }
    if (
      event.target.closest("[data-drawer-close]") ||
      event.target.matches("[data-drawer-for]")
    ) {
      closeDrawers();
    }

    if (event.target.closest("[data-ads-theme]")) {
      var root = document.documentElement;
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      remember("ads-theme", next);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    closeMenus(null);
    closeDrawers();
  });

  // The sidebar's open groups. Keyed by the section's own label, so adding or reordering
  // groups cannot shuffle the stored state onto the wrong one — an index would. In the bar
  // layout this same markup is a row of dropdown MENUS, and a menu that reopens itself on the
  // next page is a bug rather than a preference.
  (function () {
    if (document.querySelector(".ads-app--horizontal")) return;
    var groups = document.querySelectorAll(".ads-sidebar [data-nav-group]");
    if (!groups.length) return;

    var open = null;
    try {
      open = JSON.parse(recall("ads-nav-open") || "null");
    } catch (error) {
      open = null;
    }
    if (open) {
      groups.forEach(function (group) {
        var name = group.getAttribute("data-nav-group");
        // a group the reader has never touched keeps the server's answer
        if (Object.prototype.hasOwnProperty.call(open, name)) group.open = open[name];
      });
    }

    groups.forEach(function (group) {
      group.addEventListener("toggle", function () {
        var state = {};
        groups.forEach(function (each) {
          state[each.getAttribute("data-nav-group")] = each.open;
        });
        remember("ads-nav-open", JSON.stringify(state));
      });
    });
  })();

  // The menu button. One control, two jobs, because the room decides which one makes sense:
  // wide, it folds the sidebar to a rail and back, and the choice is remembered (restored
  // before first paint by the shell); narrow, it opens the sidebar as a panel over the page.
  // `aria-expanded` says which state the reader is in, and the stylesheet keys off it.
  (function () {
    var button = document.querySelector("[data-ads-sidebar]");
    var app = document.querySelector(".ads-app");
    var sidebar = document.getElementById("ads-sidebar");
    if (!button || !app || !sidebar) return;
    var narrow = window.matchMedia("(max-width: 47.99em)");

    function sync() {
      var open = !narrow.matches && !app.classList.contains("ads-app--folded");
      button.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function closePanel(refocus) {
      if (!narrow.matches || button.getAttribute("aria-expanded") !== "true") return;
      button.setAttribute("aria-expanded", "false");
      if (refocus) button.focus();
    }

    button.addEventListener("click", function () {
      if (narrow.matches) {
        var opening = button.getAttribute("aria-expanded") !== "true";
        button.setAttribute("aria-expanded", opening ? "true" : "false");
        if (opening) {
          var first = sidebar.querySelector("[href], button, summary");
          if (first) first.focus();
        }
        return;
      }
      var folded = app.classList.toggle("ads-app--folded");
      remember("ads-sidebar-folded", folded ? "1" : "0");
      sync();
    });

    document.addEventListener("click", function (event) {
      if (!sidebar.contains(event.target) && !button.contains(event.target)) closePanel(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closePanel(sidebar.contains(document.activeElement));
    });
    narrow.addEventListener("change", sync);
    sync();
  })();

  // The lightbox. ONE dialog for the page, because a dialog per thumbnail is a hundred
  // elements that are `display: none` and still in the accessibility tree's way. The page
  // supplies `#ads-lightbox`; a trigger carries `data-lightbox` (the image), and optionally
  // `data-lightbox-alt` and `data-lightbox-title`.
  (function () {
    var box = document.getElementById("ads-lightbox");
    if (!box) return;
    var image = box.querySelector("img");
    var title = box.querySelector("strong");
    document.addEventListener("click", function (event) {
      var opener = event.target.closest("[data-lightbox]");
      if (opener) {
        image.src = opener.getAttribute("data-lightbox");
        image.alt = opener.getAttribute("data-lightbox-alt") || "";
        title.textContent = opener.getAttribute("data-lightbox-title") || image.alt;
        // showModal, not show: the person asked for this one, so it takes the focus and
        // gives it back to the trigger on close — which <dialog> does for us
        box.showModal();
        return;
      }
      // the backdrop is the dialog's own box outside its children, so a click that lands on
      // the dialog element itself is a click on the backdrop
      if (event.target === box || event.target.closest("[data-lightbox-close]")) box.close();
    });
  })();

  // Section nav: mark the link whose section is on screen. An IntersectionObserver rather than
  // a scroll handler — the browser already knows, and asking it on every scroll frame is the
  // classic way a long page starts to feel heavy.
  document.querySelectorAll("[data-spy]").forEach(function (nav) {
    var links = [].slice.call(nav.querySelectorAll("a[href^='#']"));
    var sections = links
      .map(function (link) { return document.getElementById(link.getAttribute("href").slice(1)); })
      .filter(Boolean);
    if (!sections.length) return;
    var seen = new Map();
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) { seen.set(entry.target, entry.isIntersecting); });
        var current = sections.find(function (section) { return seen.get(section); });
        links.forEach(function (link) {
          // not `toggleAttribute`: it sets the attribute EMPTY, and `aria-current=""` is a
          // present-but-meaningless attribute that still matches `[aria-current]`
          if (current && link.getAttribute("href") === "#" + current.id) {
            link.setAttribute("aria-current", "true");
          } else {
            link.removeAttribute("aria-current");
          }
        });
      },
      // the top third of the viewport: a heading is "the section you are reading" from the
      // moment it reaches the upper part of the screen, not when it is dead centre
      { rootMargin: "0px 0px -66% 0px" }
    );
    sections.forEach(function (section) { observer.observe(section); });
  });

  window.adsDrawer = { open: toggleDrawer, closeAll: closeDrawers };
})();
