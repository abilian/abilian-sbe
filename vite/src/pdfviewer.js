/* The PDF viewer, on the one page that shows a document as PDF
 * (documents/view_pdf.html). PDF.js renders the pages into the page itself.
 *
 * Its worker, character maps, standard fonts and image decoders are files of
 * their own, which `npm run build` copies to static/vite/pdfjs-<version>/. The
 * version is in the path because static files are cached for a year: after an
 * upgrade, a cached worker of another version would refuse to run.
 */
import { GlobalWorkerOptions, getDocument, version } from "pdfjs-dist";
import {
  EventBus,
  PDFLinkService,
  PDFViewer,
} from "pdfjs-dist/web/pdf_viewer.mjs";

async function showPdf(root) {
  const { pdfUrl, viteUrl } = root.dataset;
  const assetsUrl = `${viteUrl}pdfjs-${version}/`;
  GlobalWorkerOptions.workerSrc = `${assetsUrl}pdf.worker.min.mjs`;

  const eventBus = new EventBus();
  const linkService = new PDFLinkService({ eventBus });
  const container = root.querySelector(".pdf-container");
  const viewer = new PDFViewer({ container, eventBus, linkService });
  linkService.setViewer(viewer);

  const pageNumber = root.querySelector("[data-page-number]");
  eventBus.on("pagesinit", () => {
    viewer.currentScaleValue = "page-width";
  });
  eventBus.on("pagechanging", (event) => {
    pageNumber.value = event.pageNumber;
  });
  pageNumber.addEventListener("change", () => {
    viewer.currentPageNumber = Number(pageNumber.value);
  });
  root
    .querySelector("[data-zoom-in]")
    .addEventListener("click", () => viewer.increaseScale());
  root
    .querySelector("[data-zoom-out]")
    .addEventListener("click", () => viewer.decreaseScale());

  const pdf = await getDocument({
    url: pdfUrl,
    cMapUrl: `${assetsUrl}cmaps/`,
    standardFontDataUrl: `${assetsUrl}standard_fonts/`,
    wasmUrl: `${assetsUrl}wasm/`,
    // The Content Security Policy does not allow 'wasm-unsafe-eval', so
    // WebAssembly cannot start: the image decoders run their JavaScript
    // versions, imported from wasmUrl, instead.
    useWasm: false,
    // A PDF's own scripts do not run.
    enableScripting: false,
  }).promise;

  viewer.setDocument(pdf);
  linkService.setDocument(pdf);
  pageNumber.max = pdf.numPages;
  root.querySelector("[data-page-count]").textContent = pdf.numPages;
  root.dataset.pages = pdf.numPages;
}

const root = document.getElementById("pdf-viewer");
if (root) {
  showPdf(root);
}
