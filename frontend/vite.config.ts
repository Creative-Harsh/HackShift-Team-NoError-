import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import process from 'node:process'

export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'pashuraksha-offline-shell', enforce: 'post',
    generateBundle(_, bundle) {
      const files=[...Object.keys(bundle).map(name=>'/'+name),'/index.html','/manifest.webmanifest','/icon.svg']
      const assets=JSON.stringify([...new Set(files)].sort())
      const version=createHash('sha256').update(assets).digest('hex').slice(0,12)
      const template=readFileSync(new URL('./scripts/sw-template.js',import.meta.url),'utf8')
      this.emitFile({type:'asset',fileName:'sw.js',source:template.replace('__PRECACHE__',assets).replace('__VERSION__',version)})
    }
  }],
  server: { proxy: { '/api': process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000' } },
  preview: { proxy: { '/api': process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000' } },
  build: { sourcemap: false },
})
