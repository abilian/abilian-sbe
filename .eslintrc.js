// {
//     'rules': {
//         'indent': [1, 2],
//         'quotes': [1, 'double'],
//         'linebreak-style': [1, 'unix'],
//         'semi': [1, 'always'],
// 	'comma-dangle': [2, 'always-multiline']
//     },
//     'env': {
//         'es6': true,
//         'browser': true
//     },
//     'extends': 'defaults/configurations/eslint'
// }


module.exports = {
  root: true,
  // https://github.com/feross/standard/blob/master/RULES.md#javascript-standard-style
  extends: 'standard',
  // required to lint *.vue files
  plugins: [
    'html'
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
    // allow paren-less arrow functions
    'arrow-parens': 0,
    // allow debugger during development
    'no-debugger': process.env.NODE_ENV === 'production' ? 2 : 0,

    'curly': 2,
    'indent': [1, 2],
    'quotes': 0,
    'linebreak-style': [1, 'unix'],
    'semi': [1, 'always'],
    'comma-dangle': [2, 'always-multiline'],
    'eqeqeq': 0,
    'space-before-function-paren': 0,
    'operator-linebreak': 0,
    'camelcase': 0,
    'padded-blocks': 0,
  },
};
