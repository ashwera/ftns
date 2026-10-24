import { useId, useState } from 'react'
import { safeSourceUrl } from './types'
import './investigation.css'

export type Investigation = {
  report_type?: 'evidence_gap'; model_review_execution?: string; failed_stage?: string | null
  company?: string; prompt?: string; run_id?: string; novelty_established?: boolean; source_scope?: string
  status: 'supported' | 'inconclusive' | 'rejected'; headline: string; summary: string; why_it_matters: string[]
  claims: { id: string; text: string; evidence_ids: string[]; assessment: 'supported' | 'contradicted' | 'unresolved'; assessment_method?: string; independently_corroborated?: boolean; verification_reason?: string; independent_groups?: string[]; citations?: { evidence_id: string; quote: string }[] }[]
  sources: { id: string; title: string; url: string; publisher: string; lineage: string; sha256: string; intake_mode: string; passages: { id: string; page: number | null; text: string }[] }[]
  timeline: { date: string; event: string; evidence_ids: string[] }[]
  calculations: { label: string; formula: string; result: number | string | null; unit: string; evidence_ids: string[] }[]
  counterargument: { text: string; evidence_ids: string[] }; falsification: string
  evidence_strength: 'Strong' | 'Moderate' | 'Weak' | 'Not rated'; strength_reasons: string[]; limitations: string[]
  decision_log: { action: string; reason: string; outcome: string }[]; completed_at: string
}

export function investigationMarkdown(i: Investigation, runId: string): string {
  return [`# ${i.headline}`, `Run: ${i.run_id ?? runId}\nCompany: ${i.company ?? 'unavailable'}\nQuestion: ${i.prompt ?? 'unavailable'}\nSource scope: ${i.source_scope ?? 'unavailable'}\nNovelty established by model challenge: ${i.novelty_established === undefined ? 'unavailable' : i.novelty_established ? 'yes' : 'no'}\nCompleted: ${i.completed_at}\nStatus: ${i.status}\nEvidence strength: ${i.evidence_strength}`, 'Exact source quotes and model challenge; this assessment is not a human audit.', i.summary,
    '## Why it matters', ...i.why_it_matters, '## Claims', ...i.claims.map(c => `${c.id} · Model challenge: ${c.assessment}: ${c.text}\nChallenge reason: ${c.verification_reason ?? 'unavailable'}\nIndependent corroboration reported: ${c.independently_corroborated === undefined ? 'unavailable' : c.independently_corroborated ? 'yes' : 'no'}\nRecorded groups: ${c.independent_groups?.join(', ') || 'unavailable'}\nEvidence: ${c.evidence_ids.join(', ') || 'unavailable'}\n${(c.citations ?? []).map(q => `Exact quote · ${q.evidence_id}\n> ${q.quote}`).join('\n\n')}`),
    '## Chronology', ...i.timeline.map(t => `${t.date}: ${t.event}\nEvidence: ${t.evidence_ids.join(', ') || 'unavailable'}`),
    '## Calculations', ...i.calculations.map(c => `${c.label}: ${c.formula} = ${c.result ?? 'unavailable'} ${c.unit}\nEvidence: ${c.evidence_ids.join(', ') || 'unavailable'}`),
    '## Counterargument', i.counterargument.text, `Evidence: ${i.counterargument.evidence_ids.join(', ') || 'unavailable'}`, '## Falsification', i.falsification,
    '## Evidence strength reasons', ...i.strength_reasons, '## Limitations', ...i.limitations,
    '## Decision log', ...i.decision_log.map(d => `${d.action}\nReason: ${d.reason}\nOutcome: ${d.outcome}`),
    '## Sources and passages', ...i.sources.map(s => `${s.id}: ${s.title}\nPublisher: ${s.publisher}\nLineage: ${s.lineage || 'unavailable'}\nIntake: ${s.intake_mode}\nSHA-256: ${s.sha256 || 'unavailable'}\nURL: ${safeSourceUrl(s.url) ?? 'unavailable'}\n${s.passages.map(p => `${p.id} · page ${p.page ?? 'unavailable'}\n> ${p.text}`).join('\n\n')}`)].join('\n\n')
}

function exportReport(i: Investigation, runId: string, format: 'json' | 'md') {
  const body = format === 'json' ? JSON.stringify({ run_id: runId, investigation: i }, null, 2) : investigationMarkdown(i, runId)
  const url = URL.createObjectURL(new Blob([body], { type: format === 'json' ? 'application/json' : 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = `investigation-${runId.replace(/[^a-zA-Z0-9_-]/g, '_')}.${format}`; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function InvestigationView({ investigation: i, runId }: { investigation: Investigation; runId: string }) {
  const prefix = useId()
  const [selected, setSelected] = useState<string | null>(null)
  const sourcesFor = (id: string) => i.sources.filter(s => s.id === id || s.passages.some(p => p.id === id))
  const evidence = (ids: string[]) => <div className="iv-evidence-links">{ids.length ? ids.map((id, index) => <button key={`${id}-${index}`} onClick={() => setSelected(id)}>Source passage: {id}</button>) : <span>Evidence references unavailable.</span>}</div>
  const source = (s: Investigation['sources'][number], passageId?: string) => <div className="iv-source" key={s.id}>
    <h4>{s.title}</h4><p>{s.publisher || 'Publisher unavailable'} · {s.id}</p>
    <dl><dt>Recorded lineage</dt><dd>{s.lineage || 'Unavailable'}</dd><dt>Intake mode</dt><dd>{s.intake_mode || 'Unavailable'}</dd><dt>SHA-256</dt><dd>{s.sha256 || 'Unavailable'}</dd></dl>
    {safeSourceUrl(s.url) ? <a href={safeSourceUrl(s.url)!} target="_blank" rel="noreferrer noopener">Open source document</a> : <p>Source URL unavailable.</p>}
    {s.passages.filter(p => !passageId || s.id === passageId || p.id === passageId).map(p => <blockquote key={p.id}><p>{p.text}</p><footer>{p.id} · {p.page === null ? 'Page unavailable' : `Page ${p.page}`}</footer></blockquote>)}
    {!s.passages.length && <p>Source passages unavailable.</p>}
  </div>
  return <article className="investigation-view" aria-label="Completed investigation">
    <header><p className="iv-overline">{i.report_type === 'evidence_gap' ? 'Evidence-gap report' : 'Completed investigation'} · {i.status}</p><h2>{i.headline}</h2><p>{i.summary}</p><p>Evidence strength: <b>{i.evidence_strength}</b> · Completed {i.completed_at}</p><p>Run: <code>{i.run_id ?? runId}</code></p>{i.company && <p>Company: {i.company}</p>}{i.prompt && <p>Run research question: {i.prompt}</p>}{i.source_scope && <p>Source scope: {i.source_scope}</p>}<p>Novelty established by model challenge: {i.novelty_established === undefined ? 'Unavailable' : i.novelty_established ? 'Yes' : 'No'}</p>{i.report_type === 'evidence_gap' ? <p>No financial conclusion accepted. Model review: {i.model_review_execution ?? 'not executed'}. {i.failed_stage && `Stage requiring recovery: ${i.failed_stage}.`}</p> : <p>Exact source quotes and model challenge. This assessment is not a human audit.</p>}</header>
    <div className="iv-exports"><button onClick={() => exportReport(i, runId, 'json')}>Export investigation JSON</button><button onClick={() => exportReport(i, runId, 'md')}>Export investigation Markdown</button></div>
    <section><h3>Why it matters</h3>{i.why_it_matters.length ? <ul>{i.why_it_matters.map((x, n) => <li key={n}>{x}</li>)}</ul> : <p>Implications unavailable.</p>}</section>
    <section><h3>Claims and model challenge</h3>{i.claims.length ? i.claims.map(c => <div className="iv-card" key={c.id}><p><b>Model challenge: {c.assessment}</b> · {c.id}</p><p>{c.text}</p><p>Challenge reason: {c.verification_reason || 'Unavailable'}</p><p>Independent corroboration reported: {c.independently_corroborated === undefined ? 'Unavailable' : c.independently_corroborated ? 'Yes' : 'No'}</p><p>Recorded lineage groups: {c.independent_groups?.join(', ') || 'Unavailable'}</p>{c.citations?.map((q, n) => <blockquote key={n}><p>{q.quote}</p><footer>Exact source quote · {q.evidence_id}</footer></blockquote>)}{evidence(c.evidence_ids)}</div>) : <p>No claims recorded.</p>}</section>
    {selected !== null && <section className="iv-selected" role="region" aria-label="Selected source passages" tabIndex={-1}><h3>Evidence reference: {selected}</h3><button onClick={() => setSelected(null)}>Close source passages</button>{sourcesFor(selected).length ? sourcesFor(selected).map(s => source(s, selected)) : <p>This evidence reference does not resolve to a source or passage in this run. Source passage unavailable.</p>}</section>}
    <section><h3>Chronology</h3>{i.timeline.length ? <ol>{i.timeline.map((t, n) => <li key={n}><p><time>{t.date}</time> · {t.event}</p>{evidence(t.evidence_ids)}</li>)}</ol> : <p>Chronology unavailable.</p>}</section>
    <section><h3>Calculations</h3>{i.calculations.length ? i.calculations.map((c, n) => <div className="iv-card" key={n}><h4>{c.label}</h4><p><code>{c.formula}</code></p><p>{typeof c.result === 'number' ? c.result.toFixed(2) : c.result ?? 'Result unavailable'} {c.unit}</p>{evidence(c.evidence_ids)}</div>) : <p>No calculations recorded.</p>}</section>
    <section><h3>Counterargument</h3><p>{i.counterargument.text || 'Counterargument unavailable.'}</p>{evidence(i.counterargument.evidence_ids)}<h3>What would falsify this assessment</h3><p>{i.falsification || 'Falsification condition unavailable.'}</p></section>
    <section><h3>Evidence strength and limitations</h3><h4>Strength reasons</h4><ul>{i.strength_reasons.map((x, n) => <li key={n}>{x}</li>)}</ul><h4>Limitations</h4>{i.limitations.length ? <ul>{i.limitations.map((x, n) => <li key={n}>{x}</li>)}</ul> : <p>No limitations recorded.</p>}<p>Lineage is shown as recorded. Different domains or publishers alone do not establish independent corroboration.</p></section>
    <section><h3>Decision log</h3>{i.decision_log.length ? <ol>{i.decision_log.map((d, n) => <li key={n}><h4>{d.action}</h4><p>Reason: {d.reason}</p><p>Outcome: {d.outcome}</p></li>)}</ol> : <p>Decision log unavailable.</p>}</section>
    <section aria-labelledby={`${prefix}-sources`}><h3 id={`${prefix}-sources`}>Source register and passages</h3>{i.sources.length ? i.sources.map(s => <details key={s.id}><summary>{s.title} · {s.id}</summary>{source(s)}</details>) : <p>No sources recorded.</p>}</section>
  </article>
}
