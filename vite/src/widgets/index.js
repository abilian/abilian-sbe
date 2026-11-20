import { initWidget } from "./registry.js";
import "./file.js";
import "./image.js";

document.querySelectorAll(".js-widget").forEach(initWidget);
