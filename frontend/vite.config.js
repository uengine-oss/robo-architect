import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'
import Components from 'unplugin-vue-components/vite'
import federation from '@originjs/vite-plugin-federation'
import { fileURLToPath, URL } from 'node:url'
import { resolve } from 'path'
import { copyFileSync, existsSync } from 'fs'

// Prefer the real open-pencil sibling repo if checked out alongside this repo.
// Fall back to the in-tree stubs (used for CI / Playwright runs without open-pencil).
const OP_REAL = resolve(__dirname, '../../../open-pencil')
const OP_STUB = resolve(__dirname, '../open-pencil')
const OP = existsSync(resolve(OP_REAL, 'src')) ? OP_REAL : OP_STUB
const FRONTEND_SRC = fileURLToPath(new URL('./src', import.meta.url))

export default defineConfig({
  plugins: [
    // Copy canvaskit.wasm from node_modules to public/
    {
      name: 'copy-canvaskit-wasm',
      buildStart() {
        const src = resolve(__dirname, 'node_modules/canvaskit-wasm/bin/canvaskit.wasm')
        const dest = resolve(__dirname, 'public/canvaskit.wasm')
        if (existsSync(src) && !existsSync(dest)) {
          copyFileSync(src, dest)
        }
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
    tailwindcss(),
    Icons({ compiler: 'vue3' }),
    Components({ resolvers: [IconsResolver({ prefix: 'icon' })], dirs: [] }),
    vue(),
    // Module Federation host — "Analysis" 탭에서 robo-analyzer-frontend 를 끼운다.
    // remote 는 build 후 5001 포트로 serve 되어야 한다(robo-data-frontend/vite.config.ts).
    federation({
      name: 'roboArchitectHost',
      remotes: {
        'robo-analyzer-frontend': 'http://localhost:5001/assets/remoteEntry.js',
      },
      shared: ['vue', 'pinia'],
    })
  ],
  build: {
    target: 'esnext'
  },
  resolve: {
    alias: {
      // NOTE: '@' alias handled by open-pencil-at-alias plugin (conditional by importer)
      // open-pencil packages (source-level)
      '@open-pencil/vue': resolve(OP, 'packages/vue/src'),
      '@open-pencil/core': resolve(OP, 'packages/core/src'),
      // open-pencil federation components shorthand
      'open-pencil-fed': resolve(OP, 'src/federation'),
      // Dependency aliases needed by open-pencil
      'opentype.js': resolve(OP, 'node_modules/opentype.js/dist/opentype.module.js'),
      // Force single Vue instance
      'vue': resolve(__dirname, 'node_modules/vue')
    }
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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
