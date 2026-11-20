// The header's language selector, made to land on the same page.
//
// Zensical renders one link per edition, each pointing at that edition's
// root: /en/, /fr/, /de/ and so on. Switching from /en/main/install/ would
// land on /fr/. This rewrites each link to the same page in the other edition,
// which exists because preprocess.py refuses to build editions whose pages
// differ. Under develop/ only the overview is translated, so from anywhere in
// that section the links go to the other edition's own develop/ page.
//
// A choice made here is remembered in a cookie, for the whole site, and the
// chooser at the site root (docs/index.html) goes straight to it next time.
//
// `zensical serve` serves one edition on its own, so there is nothing to switch
// to. When the current path is under no edition's prefix, the selector is
// hidden rather than left pointing at pages that are not there; `make preview`
// serves the whole site, where it works.
(function () {
  var COOKIE = "sbe-docs-lang";
  var ENGLISH_ONLY = "develop/";

  function remember(lang) {
    document.cookie =
      COOKIE + "=" + lang + "; path=/; max-age=31536000; SameSite=Lax";
  }

  function hide(links) {
    Array.prototype.forEach.call(links, function (link) {
      var option = link.closest(".md-header__option");
      if (option) option.hidden = true;
    });
  }

  function rewrite() {
    var links = document.querySelectorAll("a.md-select__link[hreflang]");
    if (!links.length) return;
    var editions = Array.prototype.map.call(links, function (link) {
      // The edition's root, as the theme rendered it. Kept on the link,
      // because this runs again on every instant navigation and would
      // otherwise read back the page path it wrote on the run before.
      var base = link.getAttribute("data-base");
      var known = base !== null;
      if (!known) {
        base = new URL(link.getAttribute("href"), location.href).pathname;
        link.setAttribute("data-base", base);
      }
      return {
        link: link,
        lang: link.getAttribute("hreflang"),
        base: base,
        known: known,
      };
    });

    var here = editions.filter(function (edition) {
      return location.pathname.indexOf(edition.base) === 0;
    })[0];
    if (!here) {
      hide(links);
      return;
    }

    var rest = location.pathname.slice(here.base.length);
    // develop/ is translated as one page, so the whole section lands there.
    var to = rest.indexOf(ENGLISH_ONLY) === 0 ? ENGLISH_ONLY : rest;
    editions.forEach(function (edition) {
      edition.link.setAttribute("href", edition.base + to + location.hash);
      // The theme ships a selector of its own, which ignores the href and
      // recomputes the target from location and the other edition's
      // sitemap.xml. When the page is not listed there it falls back to the
      // edition root with the trailing slash stripped -- /fr, where the
      // page's own relative assets no longer resolve and it renders unstyled.
      // Both that handler and instant navigation skip a link carrying a
      // target, so this hands the click back to the browser, which follows
      // the href above. _self is the default, so nothing else changes.
      edition.link.setAttribute("target", "_self");
      if (!edition.known) {
        edition.link.addEventListener("click", function () {
          remember(edition.lang);
        });
      }
    });
  }

  // Every other link to another edition, handed back to the browser too.
  //
  // The theme's handler does not look only at the selector: it intercepts a
  // click on any link into another edition and recomputes the destination as
  // "this page, over there". That is the selector's job and nobody else's. A
  // link from /fr/licence/ to /en/develop/patches/ ended at /en -- the
  // fallback for a page the other edition's sitemap does not list, trailing
  // slash stripped, so its relative assets no longer resolved and it rendered
  // unstyled -- and the deck's PDF link on /fr/ ended at /en/.
  //
  // The handler sits on document.body, so stopping the click here, while it
  // is still on its way down, is enough; the browser then follows the href.
  // Instant navigation stops with it, which is right across editions: another
  // edition is another base. Links the loop above has marked are left alone,
  // so the selector still records the choice.
  function editionRoots() {
    return Array.prototype.map.call(
      document.querySelectorAll("link[rel=alternate][hreflang]"),
      function (link) {
        return new URL(link.getAttribute("href"), location.href).pathname;
      }
    );
  }

  document.addEventListener(
    "click",
    function (event) {
      if (!(event.target instanceof Element)) return;
      var link = event.target.closest("a[href]");
      if (!link || link.target) return;
      var path = new URL(link.href, location.href).pathname;
      var root = editionRoots().filter(function (base) {
        return path.indexOf(base) === 0;
      })[0];
      if (root && location.pathname.indexOf(root) !== 0) event.stopPropagation();
    },
    true
  );

  rewrite();
  // navigation.instant swaps pages without a reload and rebuilds the header,
  // so the links are rewritten after every swap.
  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(rewrite);
  }
})();
