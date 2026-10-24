import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const files: Record<string, string> = {
  audit: 'outputs/dataset_audit.json',
  readiness: 'outputs/research_readiness.json',
  evidence: 'data/processed_step6/evidence.jsonl',
  ingestion: 'data/processed_step6/ingestion_report.json',
  f1: 'outputs/f1_output.json',
  r1: 'outputs/r1_plan.json',
  companies: 'data/company_registry.json',
  claims: 'data/claims_step1/claims.jsonl',
  'claim-report': 'data/claims_step1/extraction_report.json',
}

function localResearchData(): Plugin {
  return {
    name: 'signalforge-local-research-data',
    configureServer(server) {
      server.middlewares.use('/api/research', async (req, res) => {
        const key = new URL(req.url ?? '/', 'http://localhost').pathname.replace(/^\//, '')
        const file = files[key]
        if (!file || req.method !== 'GET') {
          res.statusCode = 404
          res.end(JSON.stringify({ error: 'Unknown read-only research resource.' }))
          return
        }
        try {
          const body = await readFile(resolve(root, file), 'utf8')
          res.setHeader('Content-Type', key === 'evidence' ? 'application/x-ndjson; charset=utf-8' : 'application/json; charset=utf-8')
          res.setHeader('Cache-Control', 'no-store')
          res.end(body)
        } catch {
          res.statusCode = 404
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(JSON.stringify({ error: `${key} output is not available yet.` }))
        }
      })
    },
  }
}

export default defineConfig({ plugins: [react(), localResearchData()], server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api/agent': { target: 'http://127.0.0.1:8765', changeOrigin: true } } } })
