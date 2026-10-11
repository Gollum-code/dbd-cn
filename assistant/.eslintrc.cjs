module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: ["eslint:recommended", "plugin:vue/vue3-recommended"],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
  },
  rules: {
    "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "vue/multi-word-component-names": "off",
    "vue/max-attributes-per-line": "off",
    "vue/singleline-html-element-content-newline": "off",
    "vue/html-self-closing": "off",
    "vue/html-indent": "off",
    "vue/html-closing-bracket-newline": "off",
    "vue/attributes-order": "off",
    "vue/first-attribute-linebreak": "off",
  },
  ignorePatterns: ["dist/", "node_modules/", "src-tauri/"],
};