/* ESLint config for the desktop/ Electron shell (TypeScript, Node/CommonJS). */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "script",
    project: ["./tsconfig.main.json", "./tsconfig.preload.json"],
    tsconfigRootDir: __dirname,
  },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  env: {
    node: true,
    es2022: true,
  },
  rules: {
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "@typescript-eslint/consistent-type-imports": "warn",
    "no-console": "off",
  },
  ignorePatterns: ["dist/", "out/", "resources/python/", "resources/neo4j/", "node_modules/"],
  overrides: [
    {
      files: ["tests/**/*.ts"],
      env: { node: true },
    },
  ],
};
