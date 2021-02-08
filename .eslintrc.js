module.exports = {
  root: true,
  // See: https://github.com/prettier/eslint-config-prettier
  // and: https://github.com/feross/standard/blob/master/RULES.md#javascript-standard-style
  extends: ["prettier", "prettier/standard", "plugin:requirejs/recommended"],
  // required to lint *.vue files
  plugins: ["html", "requirejs"],
  env: {
    browser: true,
    es6: true,
  },
  // add your custom rules here
  rules: {
    semi: ["error", "always"],
    curly: "error",
    // "space-before-function-paren": ["warn"],
  },
};
