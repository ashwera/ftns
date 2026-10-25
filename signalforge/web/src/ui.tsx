import { useEffect, useMemo, useRef, useState } from 'react'
import { categoryLabels, loadResearchData, safeSourceUrl, type Claim, type Evidence, type ResearchData } from './types'
import { loadFindingBundle, type FindingBundle } from './finding'
import Signal from './signal'
import InvestigationView from './investigation'
import { DEMO_COMPANY, DEMO_RUN_ID, SHOW_LEGACY_SAVED_RUN } from './demo-run'
import { ACTIVE, ApiError, MAX_POLL_FAILURES, POLL_MS, RUN_ID, getRun, isLiveRun, listRuns, normalizeInvestigation, outcome, reportMismatch, stageLabel, stageTone, startRun, type LiveRun, type RunSummary } from './live-run'

type View = 'signal' | 'overview' | 'claims' | 'evidence' | 'angles'
const initial: ResearchData = { audit: null, readiness: null, evidence: [], ingestion: null, f1: null, r1: null, companies: [], claims: [], claimReport: null, unavailable: [] }
const fmtDate = (value?: string | null) => { if (!value) return null; const date = new Date(value); return Number.isNaN(date.valueOf()) ? null : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }) }
const titleCase = (s?: string | null) => (s || 'unknown').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())

const LAST_RUN_KEY = 'signalforge.lastResearchRun'
const storage = { get: () => { try { return localStorage.getItem(LAST_RUN_KEY) } catch { return null } }, set: (id: string) => { try { localStorage.setItem(LAST_RUN_KEY, id) } catch { /* private mode */ } } }
const DEFAULT_PROMPT = 'Whether announced capacity additions materially diverge from actually commissioned capacity.'
type Origin = 'new' | 'saved' | 'restored'

export function StartResearch() {
  const [company, setCompany] = useState('')
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [run, setRun] = useState<LiveRun | null>(null)
  const [origin, setOrigin] = useState<Origin>('new')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [pollStopped, setPollStopped] = useState(false)
  const [pollKick, setPollKick] = useState(0)
  const [savedRuns, setSavedRuns] = useState<RunSummary[]>([])
  const [runsError, setRunsError] = useState('')
  const [opening, setOpening] = useState(false)
  const currentId = useRef<string | null>(null)
  const request = useRef(0)
  const active = !!run && ACTIVE.has(run.status)
  const show = (next: LiveRun | null, from: Origin) => { currentId.current = next?.run_id ?? null; setRun(next); setOrigin(from); setPollError(''); setPollStopped(false) }

  useEffect(() => {
    const controller = new AbortController()
    listRuns(controller.signal).then(body => {
      if (!Array.isArray(body.runs)) throw new Error()
      setSavedRuns(body.runs); setRunsError('')
    }).catch(() => { if (!controller.signal.aborted) setRunsError('Saved runs unavailable. The local research service may be offline.') })
    return () => controller.abort()
  }, [run?.status, run?.run_id])

  // Reopening the workspace restores the last run you opened, labelled as such — never silently.
  useEffect(() => {
    const id = storage.get()
    if (!id || !RUN_ID.test(id)) return
    const controller = new AbortController()
    const token = ++request.current
    getRun(id, controller.signal).then(saved => {
      if (token !== request.current || !isLiveRun(saved) || saved.run_id !== id) return
      show(saved, 'restored'); setCompany(saved.company); setPrompt(saved.prompt)
    }).catch(() => {})
    return () => controller.abort()
  }, [])

  async function openSaved(id: string) {
    if (!id) return
    const token = ++request.current
    setOpening(true); setError('')
    try {
      const saved = await getRun(id)
      if (token !== request.current) return
      if (!isLiveRun(saved) || saved.run_id !== id) throw new Error()
      show(saved, 'saved'); setCompany(saved.company); setPrompt(saved.prompt); storage.set(saved.run_id)
    } catch { if (token === request.current) setError('Saved run could not be opened. Nothing else was changed.') }
    finally { if (token === request.current) setOpening(false) }
  }

  useEffect(() => {
    if (!active || !run || pollStopped) return
    const id = run.run_id
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    let failures = 0
    async function poll() {
      try {
        const next = await getRun(id, controller.signal)
        if (controller.signal.aborted || currentId.current !== id) return
        if (!isLiveRun(next) || next.run_id !== id) throw new ApiError('Status response did not match this run.')
        failures = 0; setPollError(''); setRun(next)
        if (!ACTIVE.has(next.status)) return
      } catch (cause) {
        if (controller.signal.aborted) return
        failures += 1
        const message = cause instanceof Error ? cause.message : 'Status unavailable.'
        if ((cause instanceof ApiError && cause.status === 404) || failures >= MAX_POLL_FAILURES) {
          setPollStopped(true)
          setPollError(cause instanceof ApiError && cause.status === 404 ? `Run ${id} was not found on the research service. Status checks stopped.`
            : `Status checks stopped after ${failures} failed attempts (${message}) The run may still be executing on the service; its last known state is shown and is not final.`)
          return
        }
        setPollError(`Status check failed (${message}) Retrying ${failures}/${MAX_POLL_FAILURES}…`)
      }
      timer = setTimeout(poll, POLL_MS * Math.max(1, failures))
    }
    timer = setTimeout(poll, 500)
    return () => { controller.abort(); clearTimeout(timer) }
  }, [active, run?.run_id, pollStopped, pollKick])

  async function start() {
    const c = company.trim(), q = prompt.trim()
    if (!c || !q) { setError('Enter both a company and a research question.'); return }
    request.current++
    show(null, 'new'); setPending(true); setError('')
    try {
      const body = await startRun(c, q)
      if (!isLiveRun(body) || !RUN_ID.test(body.run_id)) throw new ApiError('Research service accepted the request but returned no valid run ID.')
      show(body, 'new'); storage.set(body.run_id)
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : undefined
      setError(status === 409 ? 'Another research run is already active on the service. Wait for it to finish, or open it from Saved investigations to follow its progress.'
        : status === 400 ? 'The service rejected the input: company must be 1–200 characters and the question 1–4000 characters.'
        : cause instanceof Error ? cause.message : 'Research could not start.')
    } finally { setPending(false) }
  }

  const editedAway = !!run && !active && (company.trim() !== run.company || prompt.trim() !== run.prompt)
  return <section aria-label="Start research" className="weight-card" style={{ display: 'block', marginBottom: 24 }}>
    <h2>Start research</h2><p>Runs the latest research workflow on the local service for any company: public-source discovery, evidence checks, F1 angle selection, R1 planning and investigation using the backend's configured model. Each stage reports its real outcome; evidence gates can stop F1/R1.</p>
    <p>The default question is selected from the handover; exact judge-assigned wording has not been provided.</p>
    <button type="button" className="quiet-link" disabled={pending || active || opening} onClick={() => { setCompany('NTPC Limited'); setPrompt('For NTPC North Karanpura Unit 3, compare announced capacity additions with actually commissioned capacity at the FY2024-25 cutoff. Find primary passages for expected completion, trial completion and commercial operation dates, and distinguish each milestone before assessing any divergence.') }}>Use focused NTPC example · North Karanpura Unit 3</button>
    <div className="saved-runs"><label htmlFor="saved-research-run">Saved investigations</label><select id="saved-research-run" value={savedRuns.some(s => s.run_id === run?.run_id) ? run!.run_id : ''} onChange={event => void openSaved(event.target.value)} disabled={active || pending || opening}><option value="">Choose a saved run</option>{savedRuns.map(s => <option key={s.run_id} value={s.run_id}>{s.company} · {s.prompt.slice(0, 90)} · {s.status} · {s.created_at}</option>)}</select>{runsError && <p>{runsError}</p>}{opening && <p role="status">Opening saved investigation…</p>}{!runsError && !savedRuns.length && <p>No saved runs available.</p>}</div>
    <form noValidate onSubmit={event => { event.preventDefault(); void start() }}>
      <label htmlFor="research-company">Company</label><input id="research-company" value={company} onChange={e => setCompany(e.target.value)} maxLength={200} required placeholder="Company to investigate, e.g. the judge-assigned issuer" disabled={pending || active} style={{ display: 'block', width: '100%', margin: '8px 0 16px' }}/>
      <label htmlFor="research-prompt">Research question</label><textarea id="research-prompt" value={prompt} onChange={e => setPrompt(e.target.value)} maxLength={4000} required rows={3} disabled={pending || active} style={{ display: 'block', width: '100%', margin: '8px 0 16px' }}/>
      <button className="run-button" type="submit" disabled={pending || active}>{pending ? 'Starting…' : active ? 'Research running…' : 'Start research'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {pending && <p role="status">Submitting to the research service…</p>}
    {run && <RunReport run={run} heading={origin === 'new' ? 'Current run' : origin === 'saved' ? 'Saved run' : 'Restored run'}
      note={origin !== 'new' ? `${origin === 'restored' ? 'Restored from your last session' : 'Opened from saved investigations'}; created ${run.created_at}. This is not a new run. Enter a company and start research to run a new investigation.` : undefined}>
      {editedAway && <p role="note">The form now differs from this run. The result below still belongs to {run.company}; it has not been re-run for your edits.</p>}
      {pollError && <p role="alert">{pollError}</p>}
      {pollStopped && active && <button type="button" className="quiet-link" onClick={() => { setPollStopped(false); setPollError(''); setPollKick(k => k + 1) }}>Resume status checks</button>}
      {active && !pollStopped && <p role="status">Investigation in progress. Local model inference can take several minutes; status is checked every {POLL_MS / 1000} seconds.</p>}
    </RunReport>}
  </section>
}

/** One run's real stages, errors and report — shared by live runs and the pinned demo run. */
export function RunReport({ run, heading, note, children }: { run: LiveRun; heading: string; note?: string; children?: React.ReactNode }) {
  const status = outcome(run)
  const mismatch = reportMismatch(run)
  const active = ACTIVE.has(run.status)
  return <div className="live-run" data-run-id={run.run_id}>
      <h3>{heading} · {run.company} · <span className={`workflow-status ${status.tone}`}>{status.label}</span></h3>
      {note && <p>{note}</p>}
      <p>Run <code>{run.run_id}</code> · Question: {run.prompt}</p>
      {run.model && <p>Last configured inference for this run: {run.model.provider} · {run.model.model}</p>}
      {children}
      {!!run.artifacts?.length && <section aria-label="Run report files"><h4>Run report files</h4><p>{(['f1.json','r1.json','investigation.json','investigation_review.json','machine_evidence_report.json'] as const).filter(name=>run.artifacts?.includes(name)).map(name=><a key={name} href={`/api/agent/runs/${encodeURIComponent(run.run_id)}/artifacts/${name}`} target="_blank" rel="noreferrer noopener" style={{marginRight:'1rem'}}>{({'f1.json':'F1 research angles','r1.json':'R1 investigation plan','investigation.json':'Final report JSON','investigation_review.json':'Model review','machine_evidence_report.json':'Evidence checks'})[name]}</a>)}</p></section>}
      {!!run.stages?.length && <ol className="workflow-list" aria-label="Run stages">{run.stages.map((s, i) => <li key={s.name}><span className="workflow-index">{String(i + 1).padStart(2, '0')}</span><div className="workflow-copy"><b>{titleCase(s.name)}</b><small>{s.detail || (s.execution === 'not_executed' ? 'Not reached in this run.' : '')}</small></div><span className={`workflow-status ${stageTone(s.execution)}`}>{stageLabel(s.execution)}</span></li>)}</ol>}
      {run.error && <div role="alert"><b>Run error{run.error.type ? ` (${run.error.type})` : ''}</b>{run.error.provider_detail && <p>{run.error.provider_detail}</p>}{!!run.error.frames?.length && <p>At: {run.error.frames.join(' → ')}</p>}</div>}
      {mismatch ? <p role="alert">The saved report does not belong to this run ({mismatch}), so it is not shown.</p>
        : run.investigation ? <>{run.investigation.report_type === 'evidence_gap' && <p>The workflow ended with an evidence-gap report: it did not establish a verified finding for {run.company}. The gaps and limitations below are the actual result.</p>}<InvestigationView key={run.run_id} investigation={normalizeInvestigation(run.investigation)} runId={run.run_id} /></>
        : !active && <p role="status">{run.status === 'completed' ? 'Final investigation unavailable for this run. F1/R1 planning output alone is not a completed investigation.' : `This run ended ${run.status} and has not produced a verified finding. See the stages above for where it stopped.`}</p>}
      <details open={!run.investigation && !active}><summary>Run execution record · {titleCase(run.status)}</summary><p>{run.company} · {run.run_id} · created {run.created_at}{run.finished_at ? ` · finished ${run.finished_at}` : ''}</p><p>Current stage: {titleCase(run.stage)}</p><ol>{(run.events ?? []).map((event, index) => <li key={index}><b>{titleCase(event.stage)}</b> — {event.message}</li>)}</ol>{!!run.discovery_actions?.length && <p>Latest source action: {titleCase(run.discovery_actions.at(-1)?.action)} · {run.discovery_actions.at(-1)?.url || run.discovery_actions.at(-1)?.query}</p>}<p>Saved locally: data/research_runs/{run.run_id}/manifest.json and events.jsonl</p>{!!run.artifacts?.length && <p>Artifacts: {run.artifacts.join(', ')}</p>}</details>
    </div>
}

/** Pinned report: a real run of the same live workflow, pinned by run ID (see demo-run.ts); polled while still active. */
export function DemoReport() {
  const [run, setRun] = useState<LiveRun | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!DEMO_RUN_ID) { setError(`No ${DEMO_COMPANY} run is pinned yet. Set DEMO_RUN_ID in web/src/demo-run.ts to a run ID.`); return }
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = () => getRun(DEMO_RUN_ID, controller.signal).then(r => { if (!isLiveRun(r) || r.run_id !== DEMO_RUN_ID) throw new ApiError('Unexpected response for the pinned run.'); setRun(r); if (ACTIVE.has(r.status)) timer = setTimeout(load, POLL_MS) })
      .catch(cause => { if (!controller.signal.aborted) setError(`${DEMO_COMPANY} report unavailable (${cause instanceof Error ? cause.message : 'error'}). The pinned run is read from the local research service.`) })
    load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])
  return <section aria-label={`${DEMO_COMPANY} report`} className="weight-card" style={{ display: 'block', marginBottom: 24 }}>
    <h2>Pinned report · {DEMO_COMPANY}</h2>
    <p>A saved run of the same live research workflow judges can run below, shown exactly as the service records it, including its current status.</p>
    {error && <p role="alert">{error}</p>}
    {!run && !error && <p role="status">Loading pinned report…</p>}
    {run && <RunReport run={run} heading="Pinned run" note={`Run created ${run.created_at}${run.finished_at ? `, finished ${run.finished_at}` : ''}.`} />}
  </section>
}

/** Demo screen: pinned Hindalco report + live workflow. The old saved run lives on in LegacyApp. */
export default function App() {
  return SHOW_LEGACY_SAVED_RUN ? <LegacyApp /> : <DemoApp />
}

function DemoApp() {
  const [view, setView] = useState<'ntpc' | 'live' | 'old'>('ntpc')
  const tabs: ['ntpc' | 'live' | 'old', string][] = [['ntpc', 'Hindalco report'], ['live', 'Live research'], ['old', 'Old NTPC report']]
  return <div className="app-shell">
    <aside className="rail">
      <a className="brand" href="#top" aria-label="SignalForge home"><span className="brand-mark">S<span>F</span></span><span className="brand-copy"><strong>SignalForge</strong><small>RESEARCH SYSTEM</small></span></a>
      <div className="rail-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="nav-list">{tabs.map(([id, label], i) => <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => setView(id)}><span className="nav-index">0{i + 1}</span>{label}</button>)}</nav>
      <div className="rail-bottom"><div className="rail-label">SYSTEM</div><div className="rail-note">Research leads and evidence gaps are not verified findings.</div><div className="rail-version">LOCAL WORKSPACE <span>v0.1</span></div></div>
    </aside>
    <main id="top" className="main">
      <header className="topbar"><div className="breadcrumb">Energy, Power & Renewables <span>/</span> {tabs.find(t => t[0] === view)![1]}</div><div className="top-actions"><span className="local-tag"><i/> Local service</span></div></header>
      <div className="content">
        <div className="page-head"><div><h1>{view === 'live' ? 'Live research' : view === 'old' ? 'Old NTPC report' : DEMO_COMPANY}</h1></div></div>
        {view === 'ntpc' ? <DemoReport /> : view === 'live' ? <StartResearch /> : <OldReport />}
      </div>
    </main>
  </div>
}

/** The earlier saved batch-pipeline report (public/data/finding, run_20261024_ntpc_recovered), shown as history. */
function OldReport() {
  const [bundle, setBundle] = useState<FindingBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { loadFindingBundle().then(r => 'error' in r ? setError(r.error) : setBundle(r)) }, [])
  return <>
    <p className="section-eyebrow">HISTORICAL SAVED RUN · earlier batch pipeline · Not produced by the live workflow</p>
    <p>Pipeline provenance below reflects that run's configuration at the time (for example its F1 status); it does not describe the current model setup.</p>
    <Signal bundle={bundle} error={error} evidenceIds={new Set()} onEvidence={() => {}} />
  </>
}

export function LegacyApp() {
  const [data, setData] = useState(initial)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<View>('signal')
  const [bundle, setBundle] = useState<FindingBundle | null>(null)
  const [findingError, setFindingError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Evidence | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('all')
  const [verified, setVerified] = useState('all')
  const [dateFilter, setDateFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [claimQuery, setClaimQuery] = useState('')
  const [claimStatus, setClaimStatus] = useState('all')
  const [companyName, setCompanyName] = useState('NTPC Limited')

  useEffect(() => { loadResearchData().then(setData).finally(() => setLoading(false)) }, [])
  useEffect(() => { loadFindingBundle().then(r => 'error' in r ? setFindingError(r.error) : setBundle(r)) }, [])
  const evidenceIds = useMemo(() => new Set(data.evidence.map(e => e.evidence_id)), [data.evidence])
  useEffect(() => { if (location.hash.startsWith('#evidence=')) { setView('evidence'); setSelected(data.evidence.find(e => e.evidence_id === location.hash.slice(10)) ?? null) } }, [data.evidence])
  const docs = useMemo(() => [...new Set(data.evidence.map(e => e.document_title))], [data.evidence])
  const companyClaims = useMemo(() => data.claims.filter(claim => claim.entity === companyName), [data.claims, companyName])
  const filteredClaims = useMemo(() => companyClaims.filter(claim => {
    const search = `${claim.claim_id} ${claim.source_path} ${claim.metric ?? ''} ${claim.raw_metric_text ?? ''} ${claim.raw_value_text} ${claim.raw_unit_text} ${claim.source_excerpt}`.toLowerCase()
    return search.includes(claimQuery.toLowerCase()) && (claimStatus === 'all' || claim.extraction_status === claimStatus)
  }), [companyClaims, claimQuery, claimStatus])
  const displayEvidence = useMemo(() => data.evidence.filter(e => {
    const search = `${e.document_title} ${e.excerpt_or_fact} ${e.evidence_id} ${e.source_organization ?? ''} ${e.related_claim ?? ''}`.toLowerCase()
    return search.includes(query.toLowerCase()) && (kind === 'all' || e.information_type === kind) && (verified === 'all' || e.claim_verification_status === verified) && (!sourceFilter || e.document_title === sourceFilter) && (!dateFilter || [e.event_date, e.publication_date, e.reporting_period].some(d => d?.includes(dateFilter)))
  }).slice(0, 100), [data.evidence, query, kind, verified, sourceFilter, dateFilter])
  const selectEvidence = (e: Evidence) => { setSelected(e); setView('evidence'); location.hash = `evidence=${e.evidence_id}` }
  const tabs: [View, string][] = [['signal', 'Signal'], ['overview', 'Overview'], ['claims', 'Claim review'], ['evidence', 'Evidence library'], ['angles', 'Research angles']]
  const ingestion = data.ingestion ?? {}
  const counts = { total: Number(ingestion.evidence_record_count ?? data.evidence.length), verified: Number(ingestion.verified_record_count ?? 0), unresolved: Number(ingestion.unresolved_record_count ?? 0), metrics: Number(ingestion.metrics_extracted ?? 0), review: Number(ingestion.manual_review_evidence_ids_count ?? 0) }

  return <div className="app-shell">
    <aside className="rail">
      <a className="brand" href="#top" aria-label="SignalForge home"><span className="brand-mark">S<span>F</span></span><span className="brand-copy"><strong>SignalForge</strong><small>RESEARCH SYSTEM</small></span></a>
      <div className="rail-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="nav-list">{tabs.map(([id, label], i) => <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => { setView(id); setSelected(null); location.hash = id === 'signal' || id === 'overview' ? 'top' : id }}><span className="nav-index">0{i + 1}</span>{label}{id === 'evidence' && <span className="nav-count">{counts.total.toLocaleString()}</span>}{id === 'claims' && <span className="nav-count">{data.claimReport?.total_claims.toLocaleString() ?? '—'}</span>}</button>)}</nav>
      <div className="rail-bottom"><div className="rail-label">SYSTEM</div><div className="system-row"><span className="status-dot amber"/><span>Claims under review</span></div><div className="rail-note">Candidate claims are not verified findings.</div><div className="rail-version">LOCAL WORKSPACE <span>v0.1</span></div></div>
    </aside>
    <main id="top" className="main">
      <header className="topbar"><div className="breadcrumb">Energy, Power & Renewables <span>/</span> Research workspace</div><div className="top-actions"><span className="local-tag"><i/> Local data</span><button className="avatar" aria-label="Research analyst">A</button></div></header>
      <div className="content">
        {loading ? <div className="loading-state"><span className="spinner"/>Reading local research outputs…</div> : <>
      <div className="page-head"><div><h1>{view === 'signal' ? 'Signal' : view === 'overview' ? `${companyName.replace(/ Limited$/, '')} investigation` : view === 'claims' ? 'Claim review' : view === 'evidence' ? 'Evidence library' : 'Research angles'}</h1></div><div className="run-control"><label htmlFor="company-select">Saved workspace company</label><select id="company-select" aria-label="Company" value={companyName} onChange={e => setCompanyName(e.target.value)}>{data.companies.map(company => <option key={company.verified_identifier} value={company.canonical_name}>{company.canonical_name}</option>)}</select></div></div>
          <StartResearch />
          {view === 'signal' && <><p className="section-eyebrow">SAVED PRIOR RUN · NTPC · Separate from live research above</p><Signal bundle={bundle} error={findingError} evidenceIds={evidenceIds} onEvidence={id => { const e = data.evidence.find(x => x.evidence_id === id); if (e) selectEvidence(e) }} /></>}
          {view === 'overview' && <><p className="section-eyebrow">HISTORICAL SAVED WORKSPACE · {companyName} · Separate from live research above</p><Overview data={data} companyName={companyName} counts={counts} claims={companyClaims} onEvidence={selectEvidence} onViewClaims={() => setView('claims')} /></>}
          {view === 'claims' && <ClaimReview claims={filteredClaims} total={companyClaims.length} report={data.claimReport} query={claimQuery} setQuery={setClaimQuery} status={claimStatus} setStatus={setClaimStatus} onEvidence={claim => { const source = data.evidence.find(e => e.evidence_id === claim.source_chunk_id); if (source) selectEvidence(source) }} />}
          {view === 'evidence' && <EvidenceView records={displayEvidence} total={data.evidence.length} docs={docs} selected={selected} onSelect={selectEvidence} onClose={() => { setSelected(null); location.hash = 'evidence' }} query={query} setQuery={setQuery} kind={kind} setKind={setKind} verified={verified} setVerified={setVerified} dateFilter={dateFilter} setDateFilter={setDateFilter} sourceFilter={sourceFilter} setSourceFilter={setSourceFilter} />}
          {view === 'angles' && <Angles data={data} />}
          {data.unavailable.length > 0 && <footer className="source-footer">Read-only local outputs <span>·</span> Missing optional outputs: {data.unavailable.join(', ')}</footer>}
        </>}
      </div>
    </main>
  </div>
}

function Overview({ data, companyName, counts, claims, onEvidence, onViewClaims }: { data: ResearchData; companyName: string; counts: Record<string, number>; claims: Claim[]; onEvidence: (e: Evidence) => void; onViewClaims: () => void }) {
  const report = data.claimReport
  const sample = claims.slice(0, 6)
  const stageRows = [
    ['Source ingestion', report ? `${Number(data.ingestion?.document_count ?? 0)} docs · ${counts.total.toLocaleString()} blocks` : 'Output unavailable', report ? 'Complete' : 'Unavailable', report ? 'done' : 'unknown'],
    ['Claim extraction', report ? `${report.total_claims.toLocaleString()} candidate claims` : 'No extraction report', report?.run_status === 'completed' ? 'Complete' : 'Not run', report?.run_status === 'completed' ? 'done' : 'unknown'],
    ['Manual review', report ? `${report.claims_needing_attention.toLocaleString()} flagged · ${report.total_claims.toLocaleString()} unverified` : `${counts.review.toLocaleString()} source blocks waiting`, 'Outstanding', 'review'],
    ['Evidence validation', 'No corroboration output', 'Not started', 'unknown'],
    ['F1 angle selection', data.f1 ? 'F1 output available' : 'No F1 output', data.f1 ? 'Review output' : 'Not run', data.f1 ? 'done' : 'unknown'],
    ['R1 research plan', data.r1 ? 'Plan output available' : 'Requires reliable F1 output', data.r1 ? 'Plan ready' : 'Not run', data.r1 ? 'done' : 'unknown'],
  ]
  return <>
    <div className="status-line"><span className="status-mark" aria-hidden="true"/><p><b>No defensible financial finding yet.</b> Extracted filing records have not been reviewed and validated sufficiently for F1.</p><button onClick={onViewClaims}>Open claim review <span>↗</span></button></div>
    <section className="investigation-intro"><div><p className="investigation-overline">ENERGY, POWER & RENEWABLES <span>·</span> {companyName.toUpperCase()}</p><h2>Evidence is assembled.<br/>Conclusions are not.</h2><p className="intro-copy">Layer 1 extracted {report?.total_claims.toLocaleString() ?? 'no'} candidate claims. None have been verified against their source.</p></div><aside className="next-step-note"><small>Next action</small><b>Review flagged claims against their source pages</b><span>{report?.claims_needing_attention.toLocaleString() ?? '—'} {report?.claims_needing_attention === 1 ? 'candidate needs' : 'candidates need'} attention</span><button onClick={onViewClaims}>Review claims <span>→</span></button></aside></section>
    <section className="inventory-section" aria-labelledby="inventory-heading"><div className="row-section-heading"><h3 id="inventory-heading">Evidence inventory</h3><span>Step 6 ingestion report · {fmtDate(data.ingestion?.generated_at as string) || 'date unavailable'}</span></div><div className="inventory-scroll"><table className="inventory-table"><thead><tr><th scope="col">Source text blocks</th><th scope="col">Document-level identity</th><th scope="col">Normalized operating metrics</th><th scope="col">Awaiting review</th></tr></thead><tbody><tr><td>{counts.total.toLocaleString()}</td><td>{counts.verified.toLocaleString()} <small>of {counts.total.toLocaleString()}</small></td><td>{counts.metrics.toLocaleString()}</td><td>{counts.review.toLocaleString()}</td></tr></tbody></table></div><p className="inventory-note">Identity association means an exchange identifier appeared somewhere in a document. It does not verify a claim or the individual page containing it. Layer 1 separately extracted {report?.total_claims.toLocaleString() ?? '—'} unverified candidates.</p></section>
    <div className="overview-columns">
      <section className="claims-section" id="claim-review"><div className="row-section-heading"><div><h3>Claims to review</h3><p>{report ? `${report.claims_by_status.needs_review?.toLocaleString() ?? 0} need review · ${report.claims_by_status.ambiguous?.toLocaleString() ?? 0} ambiguous · ${report.claims_by_status.extracted?.toLocaleString() ?? 0} extracted, still unverified` : 'Claim extraction has not produced a report.'}</p></div><button className="quiet-link" onClick={onViewClaims}>All candidates <span>↗</span></button></div>
        {sample.length ? <ClaimTable claims={sample} onEvidence={claim => { const source = data.evidence.find(e => e.evidence_id === claim.source_chunk_id); if (source) onEvidence(source) }} /> : <div className="claims-empty"><b>{report ? 'No candidate claims match this company.' : 'No extracted claims are available yet.'}</b><p>{report ? 'The extraction report contains no company-matched candidates.' : 'When Layer 1 completes, source-linked candidates will appear here. Raw evidence remains in the evidence library.'}</p><button onClick={onViewClaims}>Open claim review <span>↗</span></button></div>}
      </section>
      <section className="workflow-section"><div className="row-section-heading"><div><h3>Historical saved pipeline stages</h3><p>From older saved output files for this workspace, not the live run above</p></div></div><ol className="workflow-list">{stageRows.map(([name, detail, label, tone], i) => <li key={name}><span className="workflow-index">0{i + 1}</span><div className="workflow-copy"><b>{name}</b><small>{detail}</small></div><span className={`workflow-status ${tone}`}>{label}</span></li>)}</ol><div className="report-readiness"><b>Discovery report</b><span>Counterargument, falsification test and evidence strength are unavailable until a reliable F1 hypothesis and verified evidence exist.</span></div></section>
    </div>
  </>
}

function ClaimTable({ claims, onEvidence }: { claims: Claim[]; onEvidence: (claim: Claim) => void }) {
  return <div className="claim-table-scroll"><table className="claim-table"><thead><tr><th scope="col">Source / page</th><th scope="col">Candidate claim</th><th scope="col">Review state</th></tr></thead><tbody>{claims.map(claim => <tr key={claim.claim_id}><td><button className="claim-source" onClick={() => onEvidence(claim)}>{claim.source_path.split('/').at(-1)}<small>{claim.source_page ? `Page ${claim.source_page}` : 'Page not identified'}</small></button></td><td><button className="claim-candidate" onClick={() => onEvidence(claim)}><b>{claim.metric || claim.raw_metric_text || 'Unlabelled value'} <span>{claim.raw_value_text}{claim.raw_unit_text ? ` ${claim.raw_unit_text}` : ''}</span></b><small>{claim.source_excerpt}</small><i>{claim.period_type === 'unknown' ? 'Period unknown' : claim.period_start || claim.period_end || claim.raw_period_text || statusLabel(claim.period_type)}</i></button></td><td><span className={`claim-status ${claim.extraction_status}`}>{statusLabel(claim.extraction_status)}</span><small className="verification-state">Unverified</small><small className="claim-id">{claim.claim_id}</small></td></tr>)}</tbody></table></div>
}

function ClaimReview({ claims, total, report, query, setQuery, status, setStatus, onEvidence }: { claims: Claim[]; total: number; report: ResearchData['claimReport']; query: string; setQuery: (value: string) => void; status: string; setStatus: (value: string) => void; onEvidence: (claim: Claim) => void }) {
  return <section className="claim-review-page"><div className="claim-review-summary"><div><b>{report?.total_claims.toLocaleString() ?? '—'}</b><span>candidate claims · all unverified</span></div><div><b>{report?.claims_needing_attention.toLocaleString() ?? '—'}</b><span>flagged for attention</span></div><div><b>{report?.schema_validation_failures.toLocaleString() ?? '—'}</b><span>schema failures in extraction</span></div><p>Extraction status describes the parser result. It does not mean a claim has been checked against the filing.</p></div><div className="claim-filters"><label>Search claims<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Metric, document, excerpt or claim ID"/></label><label>Extraction state<select value={status} onChange={e => setStatus(e.target.value)}><option value="all">All states</option><option value="needs_review">Needs review</option><option value="ambiguous">Ambiguous</option><option value="extracted">Extracted</option></select></label><span>{claims.length} of {total.toLocaleString()} candidates</span></div>{claims.length ? <ClaimTable claims={claims.slice(0,100)} onEvidence={onEvidence}/> : <div className="claims-empty"><b>{report ? 'No claims match these filters.' : 'Claim extraction has not run.'}</b><p>{report ? 'Try a different term or extraction state.' : 'There are no generated candidate claims to review.'}</p></div>}{claims.length > 100 && <p className="table-limit">Showing the first 100 matches. Narrow the search to find a specific filing or claim ID.</p>}</section>
}

function statusLabel(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) }

function Angles({ data }: { data: ResearchData }) {
  const cats = data.readiness?.candidate_categories ?? []
  return <section className="angle-page"><div className="angle-banner"><div><span className="section-eyebrow">HISTORICAL SAVED F1 STATUS · not the live run above</span><h2>Ranking refused</h2><p>The F1 runner fails closed when it cannot establish company-specific evidence. No model ranking or illustrative score is substituted here.</p></div><span className="blocked-stamp">BLOCKED<br/>NO COMPANY EVIDENCE</span></div><div className="weight-card"><div><span className="section-eyebrow">CONFIGURED F1 WEIGHTS</span><h3>Scoring rubric</h3><p>Configured weights from the live research readiness output.</p></div><div className="weights">{[['Financial significance',30],['Evidence availability',25],['Testability',20],['Non-obviousness',7.5],['Cross-validation',17.5]].map(([name, n]) => <div className="weight-row" key={name as string}><span>{name}</span><div className="weight-track"><i style={{ width: `${Number(n) * 2.4}%` }}/></div><b>{data.readiness?.f1_weights[String(name).toLowerCase().replaceAll(' ','_').replace('cross-validation','cross_validation_potential')] ?? n}%</b></div>)}</div></div><div className="angle-list">{cats.map((c,i) => <div key={c.category} className="angle-card"><div className="angle-num">0{i+1}</div><div className="angle-content"><div className="angle-title"><h3>{categoryLabels[c.category]}</h3><span className="readiness-tag">{titleCase(c.readiness_rating)}</span></div><p>{c.readiness_rationale}</p><div className="angle-columns"><div><small>DATASET CAN CALCULATE</small><p>{c.relevant_metrics_calculable.length ? c.relevant_metrics_calculable.join(', ') : 'No relevant metrics.'}</p></div><div><small>MISSING EVIDENCE</small><ul>{c.evidence_missing.map(x => <li key={x}>{x}</li>)}</ul></div><div><small>NEXT ACTION</small><p>{c.recommended_next_action}</p></div></div></div></div>)}</div><div className="weights-foot">Weights: financial significance 30% · evidence availability 25% · testability 20% · non-obviousness 7.5% · cross-validation 17.5%</div></section>
}

function EvidenceView({ records, total, docs, selected, onSelect, onClose, query, setQuery, kind, setKind, verified, setVerified, dateFilter, setDateFilter, sourceFilter, setSourceFilter }: { records: Evidence[]; total: number; docs: string[]; selected: Evidence | null; onSelect: (e:Evidence)=>void; onClose:()=>void; query:string; setQuery:(s:string)=>void; kind:string; setKind:(s:string)=>void; verified:string; setVerified:(s:string)=>void; dateFilter:string; setDateFilter:(s:string)=>void; sourceFilter:string; setSourceFilter:(s:string)=>void }) {
  return <div className={`evidence-layout ${selected ? 'detail-open' : ''}`}><div className="evidence-list"><div className="library-summary"><div><b>{total.toLocaleString()}</b> extracted records</div><span>All records require manual review</span></div><div className="filters"><label className="search-box"><span>⌕</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search evidence, claims or IDs" aria-label="Search evidence"/></label><div className="filter-row"><label><span>Type</span><select value={kind} onChange={e=>setKind(e.target.value)}><option value="all">All types</option>{['reported_fact','derived_calculation','inference','unverified_hypothesis'].map(x=><option key={x} value={x}>{titleCase(x)}</option>)}</select></label><label><span>Verification</span><select value={verified} onChange={e=>setVerified(e.target.value)}><option value="all">All statuses</option>{['directly_reported','independently_corroborated','calculated','inferred','unverified'].map(x=><option key={x} value={x}>{titleCase(x)}</option>)}</select></label></div><div className="filter-row"><label><span>Document</span><select value={sourceFilter} onChange={e=>setSourceFilter(e.target.value)}><option value="">All documents</option>{docs.map(d=><option key={d}>{d}</option>)}</select></label><label><span>Date contains</span><input value={dateFilter} onChange={e=>setDateFilter(e.target.value)} placeholder="YYYY or period"/></label></div></div><div className="result-count">Showing {records.length} {records.length === 100 ? 'of first 100 matches' : 'matching records'}</div><div className="record-list">{records.map(e=><button key={e.evidence_id} className={`record-row ${selected?.evidence_id === e.evidence_id ? 'selected' : ''}`} onClick={()=>onSelect(e)}><span className={`record-marker ${e.parsing_status === 'parsed' ? 'green' : 'amber'}`}/><span className="record-info"><span className="record-tags"><i>{titleCase(e.information_type)}</i><i>{titleCase(e.claim_verification_status)}</i><i>{e.parsing_status || 'Unknown parse'}</i></span><b>{e.document_title}</b><span className="record-excerpt">{e.excerpt_or_fact.slice(0,175).replace(/\s+/g,' ')}{e.excerpt_or_fact.length>175?'…':''}</span><span className="record-meta">{e.source_path || 'No repository path'} <span>·</span> {e.source_locator || 'No locator'} <span>·</span> {e.evidence_id}</span></span><span className="record-arrow">↗</span></button>)}{!records.length && <div className="empty-inline"><b>No matching evidence records</b><p>Clear one or more filters to widen the search.</p></div>}</div></div>
    <aside className="evidence-detail">{selected ? <EvidenceDetail evidence={selected} onClose={onClose}/> : <div className="detail-empty"><span className="detail-glyph">≡</span><b>Select a record to inspect its provenance</b><p>Excerpt, source dates, identity status and extraction warnings appear here.</p></div>}</aside>
  </div>
}

function EvidenceDetail({ evidence:e, onClose }: { evidence:Evidence; onClose:()=>void }) {
  const sourceUrl = safeSourceUrl(e.source_url)
  return <div className="detail-content"><div className="detail-top"><span className="section-eyebrow">EVIDENCE RECORD</span><button onClick={onClose} aria-label="Close evidence details">×</button></div><div className="detail-id">{e.evidence_id}</div><h2>{e.document_title}</h2><div className="detail-badges"><span>{titleCase(e.information_type)}</span><span>{titleCase(e.claim_verification_status)}</span><span>{titleCase(e.parsing_status)}</span></div><div className="detail-block"><small>EXCERPT OR FACT</small><blockquote>{e.excerpt_or_fact || 'No excerpt available.'}</blockquote></div><div className="detail-block"><small>SOURCE & PROVENANCE</small><dl><dt>Organization</dt><dd>{e.source_organization || 'Not identified'}</dd><dt>Document type</dt><dd>{titleCase(e.document_type)}</dd><dt>Repository path</dt><dd className="path-value">{e.source_path || 'Unavailable'}</dd><dt>Locator</dt><dd>{e.source_locator || 'Unavailable'}{e.page_number ? ` · page ${e.page_number}` : ''}{e.table_identifier ? ` · ${e.table_identifier}` : ''}</dd><dt>Identity</dt><dd>{titleCase(e.company_identity_status)}</dd><dt>Relationship</dt><dd>{titleCase(e.source_relationship)} · duplicates are not independent evidence</dd></dl></div><div className="detail-block"><small>DATES & PERIOD</small><dl><dt>Publication</dt><dd>{fmtDate(e.publication_date) || 'Not supplied'}</dd><dt>Event</dt><dd>{fmtDate(e.event_date) || 'Not supplied'}</dd><dt>Reporting period</dt><dd>{e.reporting_period || 'Not assigned'}</dd><dt>Retrieved</dt><dd>{fmtDate(e.retrieval_date) || 'Not supplied'}</dd></dl></div>{e.metric_name && <div className="detail-block"><small>METRIC</small><p>{e.metric_name}: {e.metric_value} {e.unit} {e.currency}</p></div>}<div className="detail-block"><small>CLAIM MAPPING</small><p>{e.related_claim || 'No claim linked'}</p></div>{sourceUrl && <a className="source-link" href={sourceUrl} target="_blank" rel="noopener noreferrer">Open source document <span>↗</span></a>}<div className="warnings"><b>Extraction & verification warnings</b>{e.extraction_warnings?.length ? <ul>{e.extraction_warnings.slice(0,12).map((w,i)=><li key={i}>{w}</li>)}</ul> : <p>No extraction warnings supplied.</p>}</div></div>
}
