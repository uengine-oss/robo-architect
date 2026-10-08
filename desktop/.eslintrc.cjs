/* ESLint config for the desktop/ Electron shell (TypeScript, Node/CommonJS). */
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "script",
    // `tests/**` 는 main/preload 의 `include` 에 없다. 그래서 세 번째가 필요하다 —
    // 없으면 검사 파일마다 "Parsing error: … not found in any of the provided project(s)"
    // 가 뜨고(25개), **그 소리에 진짜 오류가 묻힌다.**
    project: ["./tsconfig.main.json", "./tsconfig.preload.json", "./tsconfig.tests.json"],
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
    // `declare module "./ipc-contract" { interface IpcRequestMap extends … {} }` 는
    // **인터페이스 병합**이고, 그 자리에서는 `type` 별칭을 쓸 수 없다. 즉 빈 몸통이
    // 문법상 필수다. 그래서 "하나만 상속하는 인터페이스" 만 열어 둔다 — 그 밖의
    // 빈 `{}` 타입은 그대로 오류로 둔다(그건 아무 값이나 받는 구멍이다).
    "@typescript-eslint/no-empty-object-type": ["error", { allowInterfaces: "with-single-extends" }],
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
