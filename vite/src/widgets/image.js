/* Image input widget: a file input that previews the image picked. SCALE and
 * FIT show all of it, CROP fills the box. */

import { FileInput } from "./file.js";
import { registerWidget } from "./registry.js";

const OBJECT_FIT = { SCALE: "contain", FIT: "contain", CROP: "cover" };

class ImageInput extends FileInput {
  constructor(node, { width = 55, height = 55, resize_mode = "FIT" } = {}) {
    super(node);
    this.width = width;
    this.height = height;
    this.objectFit = OBJECT_FIT[resize_mode] || OBJECT_FIT.FIT;
  }

  createFileItem(file) {
    const item = super.createFileItem(file);
    const preview = new Image(this.width, this.height);
    const url = URL.createObjectURL(file);

    preview.style.objectFit = this.objectFit;
    preview.addEventListener("load", () => URL.revokeObjectURL(url));
    // Not an image after all: the server will say so, and there is nothing to show.
    preview.addEventListener("error", () => {
      URL.revokeObjectURL(url);
      preview.remove();
    });
    preview.src = url;
    item.prepend(preview);
    return item;
  }
}

registerWidget(
  "imageInput",
  (node, params) => new ImageInput(node, params),
);
