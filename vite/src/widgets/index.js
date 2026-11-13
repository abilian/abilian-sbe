import { initWidget } from "./registry.js";
import "./delete.js";
import "./dynamic-row.js";
import "./file.js";
import "./image.js";

document.querySelectorAll(".js-widget").forEach(initWidget);
