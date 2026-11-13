/* Sending files: shared by the upload widgets and the folder upload dialog. */

/**
 * POST a form. XMLHttpRequest rather than fetch, which cannot report upload
 * progress.
 *
 * @param {function(number)} onProgress: called with the fraction sent, 0 to 1.
 * @returns {Promise<string>} the response text. Rejects with an Error carrying
 * the HTTP `status`: 0 when no response came (network failure, abort).
 */
export const upload = (url, body, { headers = {}, onProgress, signal } = {}) =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fail = () =>
      reject(
        Object.assign(new Error(`Upload to ${url} failed`), {
          status: xhr.status,
        }),
      );

    xhr.open("POST", url);
    Object.entries(headers).forEach(([name, value]) =>
      xhr.setRequestHeader(name, value),
    );
    xhr.upload.addEventListener("progress", (evt) => {
      if (evt.lengthComputable) {
        onProgress(evt.loaded / evt.total);
      }
    });
    xhr.addEventListener("load", () =>
      xhr.status < 400 ? resolve(xhr.responseText) : fail(),
    );
    xhr.addEventListener("error", fail);
    xhr.addEventListener("abort", fail);
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(body);
  });

export const humanSize = (size) => {
  const units = ["KB", "MB", "GB", "TB"];
  if (size <= 1024) {
    return `${size}b`;
  }
  let unit = -1;
  while (size > 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(2)}${units[unit]}`;
};
