module.exports = {
  root: true,
  // https://github.com/feross/standard/blob/master/RULES.md#javascript-standard-style
  extends: ["standard", "plugin:requirejs/recommended"],
  // required to lint *.vue files
  plugins: ["html", "requirejs"],
  env: {
    browser: true,
    es6: true,
  },
  // add your custom rules here
  rules: {
    quotes: ["error", "double", { avoidEscape: true }],
    semi: ["error", "always"],
    "comma-dangle": ["error", "always-multiline"],
    "space-before-function-paren": ["error", "never"],
    camelcase: "off",
    curly: "error",
  },
};
