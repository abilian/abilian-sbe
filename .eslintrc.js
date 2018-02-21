module.exports = {
  root: true,
  // https://github.com/feross/standard/blob/master/RULES.md#javascript-standard-style
  extends: [
    'standard',
    "plugin:requirejs/recommended",
  ],
  // required to lint *.vue files
  plugins: [
    'html', 'requirejs'
  ],
  env: {
    browser: true,
    es6: true,
  },
  globals: {
    '$': true,
  },
  // add your custom rules here
  rules: {
    'quotes': 'off',
    'semi': ['error', 'always'],
    'comma-dangle': ['error', 'always-multiline'],
    'space-before-function-paren': 'off',
    'camelcase': 'off',
    // TODO
    'eqeqeq': 'off',
    'no-throw-literal': 'off',
    'handle-callback-err': 'off',
    'no-new': 'off',
  },
  // rules: {
  //   // allow paren-less arrow functions
  //   'arrow-parens': 0,
  //   // allow debugger during development
  //   'no-debugger': process.env.NODE_ENV === 'production' ? 2 : 0,
  //
  //   'curly': 2,
  //   'indent': [1, 2],
  //   'quotes': 0,
  //   'linebreak-style': [1, 'unix'],
  //   'semi': [1, 'always'],
  //   'comma-dangle': [2, 'always-multiline'],
  //   'eqeqeq': 0,
  //   'space-before-function-paren': 0,
  //   'operator-linebreak': 0,
  //   'camelcase': 0,
  //   'padded-blocks': 0,
  // },
};
