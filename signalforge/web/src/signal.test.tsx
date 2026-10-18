// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './ui'
import { parseFinding, parseSourceCatalog, parseVerifications } from './finding'

const read = (name: string) => readFileSync(resolve(process.cwd(), 'public/data/finding', name), 'utf8')
const real = JSON.parse(read('finding_bundle.json'))
const headline = /total group renewable pipeline/
function serve(overrides: Record<string, unknown> = {}, missing: string[] = []) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input), name = url.split('/').pop() ?? ''
    if (url.includes('/data/finding/') && !missing.includes(name)) return new Response(JSON.stringify(name in overrides ? overrides[name] : JSON.parse(read(name))), { status: 200 })
    return new Response('', { status: 404 })
  }))
}
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('finding contract parser', () => {
  it('accepts the real pipeline finding unchanged and the companion verification file', () => {
    expect(parseFinding(real)).toBe(real)
    expect(parseVerifications(JSON.parse(read('verification_results.json'))).length).toBeGreaterThan(0)
    expect(parseSourceCatalog(JSON.parse(read('source_catalog_status.json')))).toHaveLength(6)
  })
  it('rejects contract violations instead of repairing them', () => {
    expect(parseFinding({ ...real, schema_version: '2.0' })).toBeNull()
    expect(parseFinding({ ...real, finding_status: 'verified_fact' })).toBeNull()
    expect(parseFinding({ ...real, evidence_strength: 'Certain' })).toBeNull()
    expect(parseFinding({ ...real, inputs: [{ ...real.inputs[0], citation: undefined }] })).toBeNull()
    expect(parseFinding({ ...real, stage_provenance: [{ stage: 'F1', execution: 'live', detail: '' }] })).toBeNull()
    expect(parseFinding(null)).toBeNull()
  })
})

describe('Signal view', () => {
  it('opens on the finding and labels it as an unverified provisional hypothesis', async () => {
    serve(); render(<App />)
    expect(await screen.findByRole('heading', { name: headline })).toBeTruthy()
    expect(screen.getByText('Provisional hypothesis')).toBeTruthy()
    expect(screen.getByText(/Not a verified conclusion/)).toBeTruthy()
    expect(screen.getByText(/inputs are not all confirmed/)).toBeTruthy()
    expect(document.body.textContent).toMatch(/No input is independently corroborated/)
    expect(screen.getByText('Weak')).toBeTruthy()
    const blocked = real.stage_provenance.filter((s: any) => s.execution === 'blocked' || s.execution === 'not_executed')
    for (const s of blocked) expect(document.body.textContent).toContain(s.detail)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0); expect(screen.getAllByText('Not executed').length).toBeGreaterThan(0)
  })
  it('shows every key input with its verification level and independence count, and every calculation', async () => {
    serve(); render(<App />); await screen.findByRole('heading', { name: headline })
    expect(screen.getAllByText('key input').length).toBe(real.audit_trail.filter((a: any) => a.key).length)
    expect(screen.getAllByText('Project text extraction only').length).toBe(real.audit_trail.filter((a: any) => a.effective_level !== 'primary_source').length)
    for (const c of real.calculations) expect(screen.getByText(c.name.replaceAll('_', ' '))).toBeTruthy()
    for (const r of real.downgrade_reasons) expect(screen.getByText(r)).toBeTruthy()
    for (const s of real.stage_provenance.filter((s: any) => s.execution === 'simulated')) expect(document.body.textContent).toContain(s.detail)
  })
  it('keeps the 709 MW derived residual separate from the direct 725 MW headline value', async () => {
    serve(); render(<App />); await screen.findByRole('heading', { name: headline })
    expect(screen.getByText('Derived residual')).toBeTruthy(); expect(screen.getByText('Direct table value')).toBeTruthy()
    expect(document.body.textContent).toContain('709 MW'); expect(document.body.textContent).toContain('725 MW')
    expect(document.querySelector('.sg-two .sg-big')?.textContent).toBe('709 MW')
    expect(document.body.textContent).toMatch(/5\.0% parent-owned/)
    expect(document.body.textContent).toContain('original pipeline-run calculations')
    expect(document.body.textContent).toContain('not NTPC’s economic ownership share')
  })
  it('keeps all seven support outcomes partial and exposes catalog not-retrieved states and the report hash', async () => {
    serve(); const user = userEvent.setup(); render(<App />); await screen.findByRole('heading', { name: headline })
    expect(real.audit_trail).toHaveLength(7)
    const rows = [...document.querySelectorAll('.sg-table:not(.sg-ratios) tbody > tr:not(.sg-detail)')]
    expect(rows).toHaveLength(7)
    for (const [index, entry] of real.audit_trail.entries()) {
      expect(entry.effective_outcome).toBe('partially_supported')
      expect(rows[index].textContent?.toLowerCase()).toContain('partially supported')
    }
    expect(document.body.textContent).not.toContain('All inputs are from the project’s own text extraction; none was checked against the original PDF.')
    expect(document.body.textContent).toContain('Run-level verification checked 6 of 7 inputs at primary-source level; 1 remained at project-text level.')
    await user.click(screen.getByText('Source catalog availability (6)'))
    expect(document.body.textContent).toContain('not retrieved')
    expect(document.body.textContent).toContain('28f32ae3803bc5aec87b49176df1e056d0cc9cf2c2a8d78f9144bc72c1b7cbbd')
    expect(document.body.textContent).toContain('network not used')
  })
  it('keeps the rounded narrative, extracted renewable amount, and detailed total as distinct source evidence', async () => {
    serve(); const user = userEvent.setup(); render(<App />); await screen.findByRole('heading', { name: headline })
    expect(document.body.textContent).toContain('14.5 GW')
    expect(document.body.textContent).toContain('13,791 MW')
    await user.click(screen.getByRole('button', { name: 're_under_implementation_jv_subsidiary' }))
    expect(document.body.textContent).toContain('14,516')
    expect(document.body.textContent).toContain('PDF page 91')
  })
  it('uses direct values for the headline and all four denominator-specific ratios', async () => {
    serve(); render(<App />); await screen.findByRole('heading', { name: headline })
    const title = screen.getByRole('heading', { name: headline })
    expect(title.textContent).toContain('5.0% parent-owned')
    expect(title.textContent).toContain('95.0% JV/subsidiary')
    expect(document.body.textContent).toContain('Share of total group renewable pipeline (14,516 MW)')
    const section = screen.getByRole('heading', { name: 'Ratios and their denominators' }).closest('section')!
    const rows = [...section.querySelectorAll('tbody tr')].map(row => row.textContent ?? '')
    expect(rows).toHaveLength(4)
    expect(rows[0]).toContain('725 MW'); expect(rows[0]).toContain('15,376 MW'); expect(rows[0]).toContain('4.7%')
    expect(rows[1]).toContain('13,791 MW'); expect(rows[1]).toContain('18,295 MW'); expect(rows[1]).toContain('75.4%')
    expect(rows[2]).toContain('13,791 MW'); expect(rows[2]).toContain('14,516 MW'); expect(rows[2]).toContain('95.0%')
    expect(rows[3]).toContain('725 MW'); expect(rows[3]).toContain('14,516 MW'); expect(rows[3]).toContain('5.0%')
    expect(section.textContent).toMatch(/different denominators and are not directly comparable/)
  })
  it('hides headline ratios when direct MW inputs are missing or inconsistent', async () => {
    const inconsistent = { ...real, inputs: real.inputs.map((input: any) => input.name === 're_under_implementation_jv_subsidiary' ? { ...input, unit: 'GW' } : input) }
    serve({ 'finding_bundle.json': inconsistent }); render(<App />)
    expect(await screen.findByRole('heading', { name: 'Renewable pipeline shares unavailable' })).toBeTruthy()
    expect(screen.getByRole('status').textContent).toMatch(/missing or inconsistent/)
    expect(screen.queryByRole('heading', { name: headline })).toBeNull()
  })
  it('expands an input to its source citation and verification results', async () => {
    serve(); const user = userEvent.setup(); render(<App />); await screen.findByRole('heading', { name: headline })
    const first = real.audit_trail.find((a: any) => a.key)
    await user.click(screen.getByRole('button', { name: first.input_name }))
    expect(await screen.findByText(first.reason, { exact: false })).toBeTruthy()
    const cite = real.inputs.find((i: any) => i.name === first.input_name).citation
    expect(document.body.textContent).toContain(cite.excerpt.slice(0, 40)); expect(document.body.textContent).toContain('no URL on record')
  })
  it('labels synthetic findings and shows a rejection plainly', async () => {
    serve({ 'finding_bundle.json': { ...real, synthetic: true } }); render(<App />)
    expect(await screen.findByText(/SYNTHETIC EXAMPLE/)).toBeTruthy(); cleanup()
    serve({ 'finding_bundle.json': { ...real, finding_status: 'no_defensible_signal', evidence_strength: 'None', rejected_hypothesis: { headline_if_inputs_held: 'Would have been X', failed_inputs: ['re_pipeline_jv_sub'] } } }); render(<App />)
    expect(await screen.findByText('Hypothesis rejected.')).toBeTruthy(); expect(screen.getByText('No defensible signal')).toBeTruthy(); expect(screen.getByText(/Nothing is claimed here/)).toBeTruthy()
  })
  it('degrades gracefully when the finding is absent or invalid, and other views still work', async () => {
    serve({}, ['finding_bundle.json']); const user = userEvent.setup(); render(<App />)
    expect(await screen.findByText('Finding not available')).toBeTruthy(); expect(screen.getByText(/npm run sync-data/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Claim review/ })); expect(await screen.findByRole('heading', { name: 'Claim review' })).toBeTruthy(); cleanup()
    serve({ 'finding_bundle.json': { ...real, schema_version: '9' } }); render(<App />)
    expect(await screen.findByText(/does not match the finding contract/)).toBeTruthy()
  })
  it('works without the run provenance file but says so', async () => {
    serve({}, ['SOURCE.json']); render(<App />); await screen.findByRole('heading', { name: headline })
    expect(screen.getByText(/Run provenance unavailable/)).toBeTruthy()
  })
})
