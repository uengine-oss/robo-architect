import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'
import Components from 'unplugin-vue-components/vite'
import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'path'
import { copyFileSync, existsSync } from 'fs'
import { createOpenPencilAliases } from '../open-pencil/vite/aliases.ts'
import { rawMarkdownPlugin } from '../open-pencil/vite/raw-markdown.ts'
import { readFileSync } from 'fs'

// Prefer the real open-pencil sibling repo if checked out alongside this repo.
// Fall back to the in-tree stubs (used for CI / Playwright runs without open-pencil).
const OP_REAL = resolve(__dirname, '../../../open-pencil')
const OP_STUB = resolve(__dirname, '../open-pencil')
// 056 — the in-tree submodule is a full open-pencil checkout (federation included);
// prefer it so worktrees/sub-checkouts never pick up a sibling repo by accident.
const OP = existsSync(resolve(OP_STUB, 'src/federation'))
  ? OP_STUB
  : existsSync(resolve(OP_REAL, 'src')) ? OP_REAL : OP_STUB
const FRONTEND_SRC = fileURLToPath(new URL('./src', import.meta.url))
const OP_VERSION = (() => {
  try { return JSON.parse(readFileSync(resolve(OP, 'package.json'), 'utf8')).version || '0.0.0' } catch { return '0.0.0' }
})()

export default defineConfig({
  // upstream open-pencil reads these compile-time constants (vite.config.ts `define`).
  // Local MCP automation is not exposed from the embedded editor, so token = null.
  define: {
    __OPENPENCIL_APP_VERSION__: JSON.stringify(OP_VERSION),
    __OPENPENCIL_LOCAL_AUTOMATION_TOKEN__: JSON.stringify(null),
    __OPENPENCIL_LOCAL_AUTOMATION_URL__: JSON.stringify('ws://127.0.0.1:7600'),
    __OPENPENCIL_LOCAL_AUTOMATION_HTTP_URL__: JSON.stringify('http://127.0.0.1:7600')
  },
  plugins: [
    // Copy canvaskit.wasm from node_modules to public/
    {
      name: 'copy-canvaskit-wasm',
      buildStart() {
        // Must match the canvaskit-wasm JS that open-pencil imports (0.41+, PathBuilder API),
        // so always take the copy from open-pencil's node_modules and overwrite stale ones.
        const src = [
          resolve(OP, 'node_modules/canvaskit-wasm/bin/canvaskit.wasm'),
          resolve(__dirname, 'node_modules/canvaskit-wasm/bin/canvaskit.wasm')
        ].find((c) => existsSync(c))
        const dest = resolve(__dirname, 'public/canvaskit.wasm')
        if (src) copyFileSync(src, dest)
      }
    },
    // Copy open-pencil bundled fonts to public/ so /Inter-Regular.ttf and
    // /NotoNaskhArabic-Regular.ttf resolve. open-pencil's loadFont() falls back
    // to these root-relative URLs when local-font access is denied and the
    // Google Fonts API key is rate-limited; without them, CanvasKit gets the
    // SPA index.html as the font payload and renders blank text.
    // Pretendard-Regular.otf is committed under public/ directly (it lives in
    // robo-architect, not open-pencil) and is preloaded as the CJK fallback
    // by features/aiDesign/fonts.js.
    {
      name: 'copy-open-pencil-fonts',
      buildStart() {
        const fonts = ['Inter-Regular.ttf', 'NotoNaskhArabic-Regular.ttf']
        for (const f of fonts) {
          const src = resolve(OP, 'public', f)
          const dest = resolve(__dirname, 'public', f)
          if (existsSync(src) && !existsSync(dest)) {
            copyFileSync(src, dest)
          }
        }
      }
    },
    // Vite plugin: override @/ resolution for open-pencil source files
    {
      name: 'open-pencil-at-alias',
      enforce: 'pre',
      resolveId(source, importer) {
        if (!source.startsWith('@/')) return null
        // open-pencil files → open-pencil/src/
        if (importer && importer.includes('/open-pencil/')) {
          return this.resolve(resolve(OP, 'src', source.slice(2)), importer, { skipSelf: true })
        }
        // robo-architect files → frontend/src/
        return this.resolve(resolve(FRONTEND_SRC, source.slice(2)), importer, { skipSelf: true })
      }
    },
    // open-pencil imports prompt/markdown files as raw strings (src/app/ai/**/*.md)
    rawMarkdownPlugin(),
    tailwindcss(),
    Icons({ compiler: 'vue3' }),
    Components({ resolvers: [IconsResolver({ prefix: 'icon' })], dirs: [] }),
    vue()
  ],
  build: {
    target: 'esnext'
  },
  resolve: {
    alias: [
      // NOTE: '@' alias handled by open-pencil-at-alias plugin (conditional by importer)
      // upstream open-pencil source-level aliases (@open-pencil/*, #core, #vue, #dom-css, fs/path shims)
      ...createOpenPencilAliases(OP).filter((entry) => entry.find !== '@'),
      // open-pencil federation components shorthand
      { find: 'open-pencil-fed', replacement: resolve(OP, 'src/federation') },
      // Single CanvasKit build shared with open-pencil (version must match public/canvaskit.wasm)
      { find: /^canvaskit-wasm$/, replacement: resolve(OP, 'node_modules/canvaskit-wasm') },
      // Force single Vue instance
      { find: /^vue$/, replacement: resolve(__dirname, 'node_modules/vue') }
    ]
  },
  optimizeDeps: {
    include: ['canvaskit-wasm', 'opentype.js', 'culori', 'fflate'],
    // yoga-layout uses top-level await which esbuild can't handle — exclude from pre-bundling
    exclude: ['yoga-layout'],
    esbuildOptions: {
      plugins: [
        {
          // esbuild plugin: override @/ resolution for open-pencil files during dep scanning
          // Also resolves file extensions (.ts, .vue, /index.ts) since esbuild needs explicit paths
          name: 'open-pencil-at-resolve',
          setup(build) {
            const extensions = ['.ts', '.vue', '.js', '/index.ts', '/index.js', '']
            build.onResolve({ filter: /^@\// }, (args) => {
              if (args.importer && args.importer.includes('/open-pencil/')) {
                const base = resolve(OP, 'src', args.path.slice(2))
                for (const ext of extensions) {
                  const full = base + ext
                  if (existsSync(full)) {
                    return { path: full }
                  }
                }
                return { path: base }
              }
              return null
            })
          }
        }
      ]
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // VITE_API_PROXY lets a worktree stack point at its own backend (e.g. :8310)
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Claude Code terminal / Figma plugin channels upgrade to WebSocket under /api
        ws: true
      }
    }
  }
})
