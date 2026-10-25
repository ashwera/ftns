// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InvestigationView, { investigationMarkdown, type Investigation } from './investigation'
import { StartResearch } from './ui'

const investigation: Investigation = {
  status: 'inconclusive', headline: 'Synthetic investigation test', summary: 'Test summary', why_it_matters: ['Test implication'],
  claims: [{ id: 'claim1', text: 'Test claim', assessment: 'unresolved', evidence_ids: ['passage1', 'missing'] }],
  sources: [{ id: 'source1', title: 'Test filing', publisher: 'Test publisher', url: 'https://example.com/filing.pdf', lineage: 'issuer-disclosure', sha256: 'abc123', intake_mode: 'cached', passages: [{ id: 'passage1', page: 12, text: 'Synthetic passage for UI tests only.' }] }],
  timeline: [{ date: '2026-01-01', event: 'Test event', evidence_ids: ['source1'] }],
  calculations: [{ label: 'Test calculation', formula: '1 / 4', result: 0.25, unit: 'ratio', evidence_ids: ['passage1'] }],
  counterargument: { text: 'Test counterargument', evidence_ids: ['source1'] }, falsification: 'Test falsification', evidence_strength: 'Weak', strength_reasons: ['Test strength reason'], limitations: ['Test limitation'], decision_log: [{ action: 'Test action', reason: 'Test reason', outcome: 'Test outcome' }], completed_at: '2026-01-02T00:00:00Z'
}
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('completed investigation', () => {
  it('keeps source-grounded planning leads visibly separate from financial claims', () => {
    const lead={question:'Did the target project commission?',citation:{evidence_id:'passage1',quote:'Synthetic capacity target for planning only.'},confidence:'Weak',why:'Issuer target requires checking.',counterargument:'Definitions may differ.',required_evidence:'A dated operator record.',lineage:'issuer:Test',date:null}
    render(<InvestigationView investigation={{...investigation,claims:[],research_leads:[lead]}} runId="lead-run" />)
    expect(screen.getByText('These questions are not verified financial findings.')).toBeTruthy()
    expect(screen.getByText(lead.citation.quote)).toBeTruthy()
    expect(investigationMarkdown({...investigation,research_leads:[lead]},'lead-run')).toContain(lead.required_evidence)
  })
  it('labels a terminal evidence gap without claiming that model review ran', () => {
    render(<InvestigationView investigation={{...investigation, report_type:'evidence_gap', claims:[], sources:[], model_review_execution:'not_executed'}} runId="gap-run" />)
    expect(screen.getByText('Evidence-gap report · inconclusive')).toBeTruthy()
    expect(screen.getByText(/No financial conclusion accepted. Model review: not_executed/)).toBeTruthy()
    expect(screen.queryByText('Completed investigation · inconclusive')).toBeNull()
  })
  it('shows exact quotes, challenge reasons and backend corroboration without inferring independence', () => {
    const expanded: Investigation = { ...investigation, company: 'Test Company', run_id: 'test-run', prompt: 'Assigned test question', novelty_established: false, source_scope: 'Bounded search', claims: [{ ...investigation.claims[0], verification_reason: 'Issuer statement only', independently_corroborated: false, independent_groups: ['issuer:canonical'], citations: [{ evidence_id: 'passage1', quote: 'Exact synthetic test quote' }] }] }
    render(<InvestigationView investigation={expanded} runId="test-run" />)
    for (const text of ['Company: Test Company', 'Run research question: Assigned test question', 'Source scope: Bounded search', 'Novelty established by model challenge: No', 'Challenge reason: Issuer statement only', 'Independent corroboration reported: No', 'Recorded lineage groups: issuer:canonical', 'Exact synthetic test quote']) expect(screen.getByText(text)).toBeTruthy()
    expect(screen.queryByText(/verified/i)).toBeNull()
    const markdown = investigationMarkdown(expanded, 'test-run')
    for (const text of ['Issuer statement only', 'issuer:canonical', 'Exact synthetic test quote', 'Bounded search', 'Assigned test question']) expect(markdown).toContain(text)
  })
  it('renders the complete contract and resolves passages, sources and missing references', async () => {
    render(<InvestigationView investigation={investigation} runId="test-run" />)
    for (const text of ['Test summary', 'Test implication', 'Test claim', 'Test counterargument', 'Test falsification', 'Test strength reason', 'Test limitation', 'Test action']) expect(screen.getByText(text)).toBeTruthy()
    expect(screen.getByText('0.25 ratio')).toBeTruthy()
    await userEvent.click(screen.getAllByRole('button', { name: 'Source passage: passage1' })[0])
    let region = screen.getByRole('region', { name: 'Selected source passages' })
    expect(within(region).getByText('Synthetic passage for UI tests only.')).toBeTruthy()
    expect(within(region).getByText('issuer-disclosure')).toBeTruthy()
    expect(within(region).getByRole('link').getAttribute('href')).toBe('https://example.com/filing.pdf')
    await userEvent.click(screen.getByRole('button', { name: 'Source passage: missing' }))
    region = screen.getByRole('region', { name: 'Selected source passages' })
    expect(within(region).getByText(/does not resolve/)).toBeTruthy()
    await userEvent.click(screen.getAllByRole('button', { name: 'Source passage: source1' })[0])
    expect(within(screen.getByRole('region', { name: 'Selected source passages' })).getByText('Synthetic passage for UI tests only.')).toBeTruthy()
  })
  it('exports the complete investigation as JSON and Markdown', async () => {
    const blobs: Blob[] = []
    vi.stubGlobal('URL', class extends URL { static createObjectURL(blob: Blob) { blobs.push(blob); return 'blob:test' } static revokeObjectURL() {} })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<InvestigationView investigation={investigation} runId="test-run" />)
    await userEvent.click(screen.getByRole('button', { name: 'Export investigation JSON' }))
    await userEvent.click(screen.getByRole('button', { name: 'Export investigation Markdown' }))
    expect(click).toHaveBeenCalledTimes(2)
    expect(blobs.map(b => b.type)).toEqual(['application/json', 'text/markdown;charset=utf-8'])
    const md = investigationMarkdown(investigation, 'test-run')
    for (const value of ['test-run', 'Test claim', 'passage1', 'Test event', '1 / 4', 'Test counterargument', 'Test falsification', 'Test limitation', 'Test outcome', 'abc123', 'issuer-disclosure', 'Synthetic passage', 'https://example.com/filing.pdf']) expect(md).toContain(value)
  })
  it('never creates unsafe document links', () => {
    render(<InvestigationView investigation={{ ...investigation, sources: [{ ...investigation.sources[0], url: 'javascript:alert(1)' }] }} runId="test-run" />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText('Source URL unavailable.')).toBeTruthy()
  })
  it.each(['supported', 'inconclusive', 'rejected'] as const)('preserves the backend %s assessment', status => {
    render(<InvestigationView investigation={{ ...investigation, status }} runId="test-run" />)
    expect(screen.getByText(`Completed investigation · ${status}`)).toBeTruthy()
  })
})

describe('saved live runs', () => {
  it('uses the handover question and offers a milestone-aware NTPC example', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }), { status: 200 })))
    render(<StartResearch />)
    expect((screen.getByLabelText('Research question') as HTMLTextAreaElement).value).toBe('Whether announced capacity additions materially diverge from actually commissioned capacity.')
    expect(screen.getByText(/exact judge-assigned wording has not been provided/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /Use focused NTPC example/ }))
    expect((screen.getByLabelText('Research question') as HTMLTextAreaElement).value).toContain('FY2024-25 cutoff')
    expect((screen.getByLabelText('Research question') as HTMLTextAreaElement).value).toContain('distinguish each milestone')
  })
  const manifest = { run_id: 'research_20261025T000000_123456abcdef', company: 'Test Company', prompt: 'Test question', status: 'completed', stage: 'complete', created_at: '2026-10-25', events: [], artifacts: [], investigation }
  it('shows the saved run provider without attributing another provider to its result', async () => {
    const saved={...manifest,model:{provider:'ollama',model:'saved-local-model'}}
    vi.stubGlobal('fetch',vi.fn(async (url:string)=>new Response(JSON.stringify(url==='/api/agent/runs'?{runs:[saved]}:saved),{status:200})))
    render(<StartResearch />)
    await screen.findByRole('option',{name:/Test Company/})
    await userEvent.selectOptions(screen.getByLabelText('Saved investigations'),saved.run_id)
    expect(await screen.findByText('Last configured inference for this run: ollama · saved-local-model')).toBeTruthy()
    expect(screen.queryByText(/grok-4.7/)).toBeNull()
  })
  it('replaces running progress with the final investigation when polling completes', async () => {
    const running = { ...manifest, status: 'running', investigation: null }
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => new Response(JSON.stringify(url === '/api/agent/runs' ? options?.method === 'POST' ? running : { runs: [] } : manifest), { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    render(<StartResearch />)
    await userEvent.click(screen.getByRole('button', { name: 'Start research' }))
    expect(await screen.findByText(/Investigation in progress/)).toBeTruthy()
    expect(await screen.findByRole('heading', { name: investigation.headline }, { timeout: 2000 })).toBeTruthy()
    expect(screen.queryByText(/Investigation in progress/)).toBeNull()
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  })
  it('loads a selected saved investigation without starting a new run', async () => {
    const { run_id, company, prompt, created_at, status, stage } = manifest
    const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/agent/runs' ? { runs: [{ run_id, company, prompt, created_at, status, stage }] } : manifest), { status: 200 }))
    vi.stubGlobal('fetch', fetcher)
    render(<StartResearch />)
    await screen.findByRole('option', { name: /Test Company/ })
    await userEvent.selectOptions(screen.getByLabelText('Saved investigations'), manifest.run_id)
    expect(await screen.findByRole('heading', { name: investigation.headline })).toBeTruthy()
    expect(screen.queryByText(/has not produced a verified finding/)).toBeNull()
    expect(fetcher.mock.calls.every(([url]) => url.startsWith('/api/agent/runs'))).toBeTruthy()
  })
  it('marks older planning-only runs as missing a final investigation', async () => {
    const old = { ...manifest, investigation: null }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/agent/runs' ? { runs: [old] } : old), { status: 200 })))
    render(<StartResearch />)
    await screen.findByRole('option', { name: /Test Company/ })
    await userEvent.selectOptions(screen.getByLabelText('Saved investigations'), old.run_id)
    expect(await screen.findByText(/F1\/R1 planning output alone/)).toBeTruthy()
  })
})
