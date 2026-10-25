// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App, { StartResearch } from './ui'
import { DEMO_RUN_ID } from './demo-run'
import type { Investigation } from './investigation'
import type { LiveRun } from './live-run'

const ID = 'research_20261025T120000_aaaaaaaaaaaa'
const OTHER = 'research_20261020T090000_bbbbbbbbbbbb'
const stages = (over: Record<string, [string, string?]>) => ['discovery', 'retrieval', 'machine_evidence', 'f1', 'r1', 'investigation', 'adjudication']
  .map(name => ({ name, execution: over[name]?.[0] ?? 'not_executed', ...(over[name]?.[1] ? { detail: over[name][1] } : {}) }))
const base = (over: Partial<LiveRun> = {}): LiveRun => ({ run_id: ID, company: 'Adani Green Energy Limited', prompt: 'Assigned question', status: 'running', stage: 'discovery', created_at: '2026-10-25T12:00:00Z', events: [], artifacts: [], stages: stages({ discovery: ['running'] }), ...over })
const gap: Investigation = { report_type: 'evidence_gap', model_review_execution: 'not_executed', company: 'Adani Green Energy Limited', run_id: ID, status: 'inconclusive', headline: 'Evidence gap: Adani Green Energy Limited', summary: 'No eligible company evidence was retrieved.', why_it_matters: [], claims: [], sources: [], timeline: [], calculations: [], counterargument: { text: '', evidence_ids: [] }, falsification: '', evidence_strength: 'Weak', strength_reasons: [], limitations: ['Search returned no issuer document.'], decision_log: [], completed_at: '2026-10-25T12:05:00Z' }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

type Route = (url: string, init?: RequestInit) => Response | Promise<Response>
function serve(route: Route) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => url === '/api/agent/runs' && init?.method !== 'POST' ? json({ runs: [] }) : route(url, init))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}
async function startFor(company: string, question = 'Assigned question') {
  const user = userEvent.setup({ advanceTimers: ms => { if (vi.isFakeTimers()) vi.advanceTimersByTime(ms) } })
  await user.type(screen.getByLabelText('Company'), company)
  await user.clear(screen.getByLabelText('Research question'))
  await user.type(screen.getByLabelText('Research question'), question)
  await user.click(screen.getByRole('button', { name: 'Start research' }))
}
const tick = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))

afterEach(() => { cleanup(); vi.useRealTimers(); localStorage.clear(); vi.unstubAllGlobals() })

describe('live research run', () => {
  it('posts exactly the entered company and question, polls that run ID and renders its genuine evidence-gap report', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let polls = 0
    const finished = base({ status: 'completed', stage: 'complete', stages: stages({ discovery: ['real'], retrieval: ['real'], machine_evidence: ['blocked', 'No retrieved original passed issuer checks.'], adjudication: ['deterministic_evidence_gap'] }), investigation: gap })
    const fetcher = serve((_url, init) => init?.method === 'POST' ? json(base({ status: 'queued', stage: 'queued' }), 202) : (polls++, json(polls < 2 ? base() : finished)))
    render(<StartResearch />)
    await startFor('Adani Green Energy Limited')
    const post = fetcher.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(String(post[1]!.body))).toEqual({ company: 'Adani Green Energy Limited', prompt: 'Assigned question' })
    expect(await screen.findByText(/Queued · not started yet/)).toBeTruthy()
    expect(screen.queryByText(/Finished/)).toBeNull()
    await tick(500); await tick(3000)
    expect(await screen.findByText('Finished · evidence-gap report, no verified finding')).toBeTruthy()
    expect(fetcher.mock.calls.filter(([url]) => url === `/api/agent/runs/${ID}`).length).toBe(2)
    expect(screen.getByRole('heading', { name: 'Evidence gap: Adani Green Energy Limited' })).toBeTruthy()
    expect(screen.getByText('Search returned no issuer document.')).toBeTruthy()
    expect(screen.getByText(/did not establish a verified finding for Adani Green Energy Limited/)).toBeTruthy()
    expect(screen.getByText('No retrieved original passed issuer checks.')).toBeTruthy()
    await tick(10000)
    expect(fetcher.mock.calls.filter(([url]) => url === `/api/agent/runs/${ID}`).length).toBe(2) // polling stopped at terminal state
    expect(screen.queryByText(/Investigation in progress/)).toBeNull()
    expect(localStorage.getItem('signalforge.lastResearchRun')).toBe(ID)
  })

  it('shows a blocked F1 with its real error and R1 as not executed, never as success', async () => {
    const blocked = base({ status: 'blocked', stage: 'f1', stages: stages({ discovery: ['real'], retrieval: ['real'], machine_evidence: ['real'], f1: ['blocked', 'Ollama model signalforge-qwen is not available at 127.0.0.1:11434.'] }) })
    serve(() => json(blocked, 202))
    render(<StartResearch />)
    await startFor('JSW Energy Limited')
    expect(await screen.findByText('Blocked at F1')).toBeTruthy()
    const rows = screen.getByRole('list', { name: 'Run stages' }).querySelectorAll('li')
    expect(rows[3].textContent).toContain('Ollama model signalforge-qwen is not available')
    expect(rows[3].textContent).toContain('Blocked')
    expect(rows[4].textContent).toContain('Not executed')
    expect(screen.getByText(/This run ended blocked and has not produced a verified finding/)).toBeTruthy()
    expect(screen.queryByText(/Completed investigation/)).toBeNull()
  })

  it('renders backend failure details and validates required input before calling the service', async () => {
    const failed = base({ status: 'failed', stage: 'f1', error: { type: 'LLMError', provider_detail: 'Model request timed out after 600 seconds.', frames: ['research_session.py:204 in execute'] } })
    const fetcher = serve(() => json(failed, 202))
    render(<StartResearch />)
    await userEvent.click(screen.getByRole('button', { name: 'Start research' }))
    expect(screen.getByRole('alert').textContent).toMatch(/Enter both a company/)
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    await startFor('Tata Power Company Limited')
    expect(await screen.findByText('Failed at F1')).toBeTruthy()
    expect(screen.getByText('Model request timed out after 600 seconds.')).toBeTruthy()
    expect(screen.getByText(/Run error \(LLMError\)/)).toBeTruthy()
  })

  it('explains a busy service (409) and an offline service without inventing a run', async () => {
    serve(() => json({ error: 'A research run is already active' }, 409))
    render(<StartResearch />)
    await startFor('NHPC Limited')
    expect((await screen.findByRole('alert')).textContent).toMatch(/already active on the service/)
    expect(screen.queryByText(/Current run/)).toBeNull()
    cleanup()
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    render(<StartResearch />)
    await startFor('NHPC Limited')
    expect((await screen.findByRole('alert')).textContent).toMatch(/Local research service unavailable.*research_service/)
  })

  it('stops polling after repeated failures and keeps the run marked as not final', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fetcher = serve((_url, init) => init?.method === 'POST' ? json(base(), 202) : json({ error: 'boom' }, 500))
    render(<StartResearch />)
    await startFor('Adani Green Energy Limited')
    await tick(500); for (let n = 1; n < 5; n++) await tick(3000 * n)
    expect((await screen.findByText(/Status checks stopped after 5 failed attempts/)).textContent).toMatch(/not final/)
    const count = fetcher.mock.calls.filter(([url]) => url === `/api/agent/runs/${ID}`).length
    await tick(60000)
    expect(fetcher.mock.calls.filter(([url]) => url === `/api/agent/runs/${ID}`).length).toBe(count)
    expect(screen.getByText(/Running · Discovery/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Resume status checks' })).toBeTruthy()
  })

  it('stops immediately when the run is not found', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    serve((_url, init) => init?.method === 'POST' ? json(base(), 202) : json({ error: 'Run not found' }, 404))
    render(<StartResearch />)
    await startFor('Adani Green Energy Limited')
    await tick(500)
    expect(await screen.findByText(/was not found on the research service/)).toBeTruthy()
  })
})

describe('separating saved and current runs', () => {
  const saved = base({ run_id: OTHER, company: 'NTPC Limited', prompt: 'Old NTPC question', status: 'completed', stage: 'complete', investigation: { ...gap, run_id: OTHER, company: 'NTPC Limited', headline: 'Saved NTPC report' } })

  it('labels a restored run on reload instead of presenting it as a new result', async () => {
    localStorage.setItem('signalforge.lastResearchRun', OTHER)
    serve(() => json(saved))
    render(<StartResearch />)
    expect(await screen.findByText(/Restored from your last session/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: /Restored run · NTPC Limited/ })).toBeTruthy()
  })

  it('clears a previous company report the moment a new run starts and never shows it under the new company', async () => {
    let release: (r: Response) => void = () => {}
    serve((_url, init) => init?.method === 'POST' ? new Promise<Response>(r => { release = r }) : json(saved))
    localStorage.setItem('signalforge.lastResearchRun', OTHER)
    render(<StartResearch />)
    expect(await screen.findByRole('heading', { name: 'Saved NTPC report' })).toBeTruthy()
    const user = userEvent.setup()
    await user.clear(screen.getByLabelText('Company')); await user.type(screen.getByLabelText('Company'), 'Adani Green Energy Limited')
    expect(screen.getByRole('note').textContent).toMatch(/still belongs to NTPC Limited/)
    await user.click(screen.getByRole('button', { name: 'Start research' }))
    expect(screen.queryByRole('heading', { name: 'Saved NTPC report' })).toBeNull()
    expect(screen.getByText('Submitting to the research service…')).toBeTruthy()
    await act(async () => release(json(base({ status: 'queued', stage: 'queued' }), 202)))
    expect(await screen.findByRole('heading', { name: /Current run · Adani Green Energy Limited/ })).toBeTruthy()
    expect(document.querySelector('.live-run')!.textContent).not.toMatch(/NTPC/)
  })

  it('refuses to render a report whose company or run ID does not match the run', async () => {
    const wrong = base({ status: 'completed', stage: 'complete', investigation: { ...gap, company: 'NTPC Limited', headline: 'Leaked NTPC report' } })
    serve(() => json(wrong, 202))
    render(<StartResearch />)
    await startFor('Adani Green Energy Limited')
    expect((await screen.findByText(/does not belong to this run/)).textContent).toMatch(/NTPC Limited/)
    expect(screen.queryByRole('heading', { name: 'Leaked NTPC report' })).toBeNull()
  })

  it('renders a partial report without crashing or inventing content', async () => {
    const partial = base({ status: 'completed', stage: 'complete', investigation: { status: 'inconclusive', headline: 'Partial report' } as Investigation })
    serve(() => json(partial, 202))
    render(<StartResearch />)
    await startFor('Adani Green Energy Limited')
    expect(await screen.findByRole('heading', { name: 'Partial report' })).toBeTruthy()
    expect(screen.getByText('No claims recorded.')).toBeTruthy()
    expect(screen.getByText('No sources recorded.')).toBeTruthy()
  })
})

describe('demo screen', () => {
  it('shows the pinned Hindalco run with its actual running status, then the evidence-gap result, and none of the old saved batch run', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const H = 'Hindalco Industries Limited'
    let polls = 0
    const running = base({ run_id: DEMO_RUN_ID, company: H, status: 'running', stage: 'adjudication', stages: stages({ investigation: ['real'], adjudication: ['running'] }) })
    const finished = base({ run_id: DEMO_RUN_ID, company: H, status: 'completed', stage: 'complete', investigation: { ...gap, run_id: DEMO_RUN_ID, company: H, headline: `Evidence gap: ${H}` } })
    const fetcher = serve(url => url === `/api/agent/runs/${DEMO_RUN_ID}` ? (polls++, json(polls < 2 ? running : finished)) : json({ error: 'unexpected' }, 404))
    render(<App />)
    expect(await screen.findByRole('heading', { name: /Pinned run · Hindalco Industries Limited · Running · Adjudication/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Hindalco report/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^\d+NTPC report/ })).toBeNull()
    expect(screen.queryByText(/Finished/)).toBeNull()
    expect(screen.queryByRole('heading', { name: `Evidence gap: ${H}` })).toBeNull()
    await tick(3000)
    expect(await screen.findByText('Finished · evidence-gap report, no verified finding')).toBeTruthy()
    expect(screen.getByText(/did not establish a verified finding for Hindalco Industries Limited/)).toBeTruthy()
    await tick(10000)
    expect(polls).toBe(2) // polling stopped at terminal state
    expect(document.body.textContent).not.toMatch(/Prepared run · NTPC/)
    expect(screen.queryByText(/SIGNALFORGE_API_KEY not configured/)).toBeNull()
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('/api/research/') || String(url).includes('data/finding'))).toBe(false)
    vi.useRealTimers()
    await userEvent.click(screen.getByRole('button', { name: /Live research/ }))
    expect(screen.getByRole('button', { name: 'Start research' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /Old NTPC report/ }))
    expect(screen.getByText(/HISTORICAL SAVED RUN · earlier batch pipeline/)).toBeTruthy()
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('data/finding/finding_bundle.json'))).toBe(true)
  })
})
