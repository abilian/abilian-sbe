// The CSP build: it parses x-* expressions itself instead of compiling them with
// `new AsyncFunction`. It takes plain expressions, not statements or arrow
// functions, and refuses x-html and assigning to DOM objects.
import Alpine from "@alpinejs/csp";
import collapse from "@alpinejs/collapse";

window.Alpine = Alpine;

// x-collapse is used in document.html, single_view.html and the audit/tag
// macros; without the plugin the directive silently does nothing.
Alpine.plugin(collapse);

Alpine.start();
