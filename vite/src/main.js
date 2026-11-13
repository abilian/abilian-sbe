// Order matters only here: Alpine starts first, as the widgets have always
// initialised after it. Every other module is self-contained and looks for its
// own elements; a module script runs once the document is parsed.
import "./alpine.js";
import "./sentry.js";
import "./modals.js";
import "./livesearch.js";
import "./picker.js";
import "./behaviors.js";
import "./widgets/index.js";
import "./documents/folder.js";
import "./documents/name-check.js";
import "./documents/upload-dialog.js";
import "./documents/viewer.js";
import "./wizard.js";
import "./forum.js";
import "./wiki.js";
import "./audit.js";
