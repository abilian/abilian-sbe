// `<div class="js-widget" data-init-with="name" data-init-params="{json}">`
// is set up by the creator registered under that name, called with the element
// and the parsed params.

const creators = new Map();

export function registerWidget(name, create) {
  creators.set(name, create);
}

export function initWidget(element) {
  const { initWith, initParams } = element.dataset;
  const create = creators.get(initWith);
  if (!create) {
    throw new Error(`Unknown widget constructor: "${initWith}"`);
  }
  create(element, initParams ? JSON.parse(initParams) : undefined);
}
