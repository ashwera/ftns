// Copies the minimum files of ONE existing pipeline run into public/data/finding/ so the dashboard works without the Vite dev middleware.
// Usage: node scripts/sync-demo-data.mjs [run_directory_name]   (default: the pinned run below)
// Read-only on ../data/runs; writes only under public/data/finding/. Never copies claims or evidence archives.
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PINNED_RUN = 'run_20261019_ntpc_slice_audit'
const FILES = ['finding_bundle.json', 'calculations.json', 'verification_results.json', 'audit_trail.json', 'stage_manifest.json']
const OPTIONAL_FILES = ['source_catalog_status.json']
const here = dirname(fileURLToPath(import.meta.url))
const runName = process.argv[2] ?? PINNED_RUN
if (!/^[A-Za-z0-9_.-]+(\/[A-Za-z0-9_.-]+)*$/.test(runName) || runName.split('/').some(part => part === '.' || part === '..')) { console.error('Invalid run name'); process.exit(2) }
const source = resolve(here, '../../data/runs', runName)
const target = resolve(here, '../public/data/finding')
const missing = FILES.filter(f => !existsSync(join(source, f)))
if (missing.length) { console.error(`Run ${runName} is missing ${missing.join(', ')}; nothing copied.`); process.exit(1) }
const finding = JSON.parse(readFileSync(join(source, 'finding_bundle.json'), 'utf8'))
if (finding.schema_version !== '1.0' || typeof finding.finding_id !== 'string') { console.error('finding_bundle.json does not look like schema 1.0; nothing copied.'); process.exit(1) }
mkdirSync(target, { recursive: true })
const copyNames = [...FILES, ...OPTIONAL_FILES.filter(name => existsSync(join(source, name)))]
const manifest = copyNames.map(name => {
  copyFileSync(join(source, name), join(target, name))
  const bytes = readFileSync(join(target, name))
  return { name, bytes: statSync(join(target, name)).size, sha256: createHash('sha256').update(bytes).digest('hex') }
})
writeFileSync(join(target, 'SOURCE.json'), JSON.stringify({ source_run: finding.run_id, source_dir: `signalforge/data/runs/${runName}`, finding_id: finding.finding_id, files: manifest, note: 'Verbatim copies of the listed run files; do not edit. Regenerate with npm run sync-data.' }, null, 2) + '\n')
console.log(`Copied ${copyNames.length} files from ${runName} to public/data/finding/`)
