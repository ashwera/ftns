import { useState } from 'react'
import type { AuditEntry, Citation, Finding, FindingBundle, FindingInput, Stage, ResearchDossier } from './finding'
import { safeSourceUrl } from './types'

const label = (s?: string | null) => (s ?? 'unknown').replaceAll('_', ' ')
const STATUS: Record<Finding['finding_status'], string> = { supported_finding: 'Supported finding', provisional_hypothesis: 'Provisional hypothesis', no_defensible_signal: 'No defensible signal' }
const num = (v: number, max = 2) => v.toLocaleString('en-IN', { maximumFractionDigits: max })
const withUnit = (v: number, unit: string | null) => `${num(v)}${unit ? ` ${unit}` : ''}`
const EXEC: Record<Stage['execution'], string> = { real: 'Real', simulated: 'Simulated', blocked: 'Blocked', not_executed: 'Not executed' }
const STAGE_NAMES: Record<string, string> = { claims_load: 'Claims', evidence_bundle: 'Evidence bundle', F1: 'F1 angle selection', R1: 'R1 research plan', source_catalog: 'Source catalog', source_verification: 'Verification', financial_signals: 'Calculations', adjudication: 'Adjudication' }

function Cite({ c, onEvidence, canOpen }: { c: Citation; onEvidence?: (id: string) => void; canOpen?: boolean }) {
  const sourceUrl = safeSourceUrl(c.url)
  return <blockquote className="sg-cite">
    <p>“{c.excerpt}”</p>
    <footer>{c.source_path ?? 'derived value'}{c.page ? ` · Source page ${c.page}` : ''}{c.locator ? ` · ${c.locator}` : ''}{sourceUrl ? <> · <a href={sourceUrl} target="_blank" rel="noreferrer noopener">official source link</a></> : ' · no URL on record'}
      {c.source_chunk_id && canOpen && onEvidence && <> · <button className="sg-link" onClick={() => onEvidence(c.source_chunk_id!)}>Open evidence record</button></>}</footer>
  </blockquote>
}

function Dossier({ dossier: d, onEvidence, evidenceIds }: { dossier: ResearchDossier | null | undefined; onEvidence: (id: string) => void; evidenceIds: Set<string> }) {
  const cites = (cs: Citation[]) => cs.length ? cs.map((c, i) => <Cite key={i} c={c} onEvidence={onEvidence} canOpen={!!c.source_chunk_id && evidenceIds.has(c.source_chunk_id)} />) : <p className="sg-sub">Source citation unavailable.</p>
  if (!d) return <section className="sg-panel" aria-label="Research dossier"><h3>Research dossier unavailable</h3><p>The optional research dossier is missing, invalid, or does not match this finding and run. Chosen prompt, implications, candidate decisions, action log and chronology are unavailable.</p></section>
  return <section className="sg-dossier" aria-label="Research dossier">
    {d.case_headline && <header className="sg-panel"><p className="sg-eyebrow">Selected case dossier · {label(d.case_status ?? 'investigation')}</p><h3>{d.case_headline}</h3><p>This investigation is separate from the saved finding above. Its inclusion does not upgrade the finding’s evidence strength.</p></header>}
    <div className="sg-panel"><h3>Chosen prompt</h3><p>{d.chosen_prompt}</p><h4>Implications</h4><ol>{d.implications.map((x, i) => <li key={i}>{x.statement}{cites(x.citations)}</li>)}</ol></div>
    <details className="sg-panel"><summary>Candidate decisions and rejected hypotheses</summary>{d.candidate_decisions.length ? d.candidate_decisions.map((x, i) => <div key={i}><h4>{x.hypothesis} · {x.decision}</h4><p>{x.reason}</p>{cites(x.citations)}</div>) : <p>Candidate decisions unavailable.</p>}</details>
    <details className="sg-panel"><summary>Agent action log</summary>{d.action_log.length ? <ol>{d.action_log.map((x, i) => <li key={i}><b>{x.action} · {EXEC[x.execution]}</b><p>{x.outcome}</p>{cites(x.citations)}</li>)}</ol> : <p>Action log unavailable.</p>}</details>
    <div className="sg-panel"><h3>Chronology</h3>{d.chronology.length ? <ol className="sg-chronology">{[...d.chronology].sort((a, b) => a.date.localeCompare(b.date)).map((x, i) => <li key={i}><time dateTime={x.date}>{x.date}</time><p>{x.event}</p>{cites(x.citations)}</li>)}</ol> : <p>Chronology unavailable.</p>}</div>
    <div className="sg-panel"><h3>Opposing evidence and counterargument</h3>{d.opposing_evidence.length ? d.opposing_evidence.map((x, i) => <div key={i}><p>{x.statement}</p>{cites(x.citations)}</div>) : <p>Opposing evidence unavailable; absence is not confirmation.</p>}{d.counterargument ? <><h4>Strongest counterargument</h4><p>{d.counterargument.statement}</p>{cites(d.counterargument.citations)}</> : <p>Counterargument unavailable.</p>}<h4>Falsification</h4>{d.falsification.length ? d.falsification.map((x, i) => <div key={i}><p>{x.statement}</p>{cites(x.citations)}</div>) : <p>Falsification evidence unavailable.</p>}</div>
  </section>
}

function downloadReport(bundle: FindingBundle, format: 'json' | 'md') {
  const f = bundle.finding, d = bundle.researchDossier
  const payload = { finding: f, research_dossier: d ?? null, source_manifest: bundle.sourceManifest, notes: bundle.notes }
  const citation = (c: Citation) => `> ${c.excerpt}\n\nSource: ${c.source_path ?? 'unavailable'}; page ${c.page ?? 'unavailable'}; ${safeSourceUrl(c.url) ?? 'URL unavailable'}`
  const statements = (xs: { statement: string; citations: Citation[] }[]) => xs.map(x => `${x.statement}\n\n${x.citations.map(citation).join('\n\n')}`).join('\n\n')
  const markdown = [`# ${f.headline}`, `Run: ${f.run_id} · Finding: ${f.finding_id}`, `${STATUS[f.finding_status]} · ${f.evidence_strength}`, f.why_it_matters,
    ...f.calculations.map(c => `## ${label(c.name)}\n${c.formula}\n\n${c.result ? `${c.result.value.toFixed(2)} ${c.result.unit}` : 'Not computed'}\n\n${c.trace}`),
    ...f.inputs.map(x => `## ${label(x.name)}\n${x.value.toFixed(2)} ${x.unit ?? ''}\n\n${citation(x.citation)}`),
    '## Limitations', ...f.limitations, '## Falsification', ...f.falsification_conditions,
    d ? `## Chosen prompt\n${d.chosen_prompt}\n\n## Implications\n${statements(d.implications)}\n\n## Candidate decisions\n${d.candidate_decisions.map(x => `${x.hypothesis} · ${x.decision}: ${x.reason}\n${x.citations.map(citation).join('\n')}`).join('\n\n')}\n\n## Action log\n${d.action_log.map(x => `${x.action} · ${x.execution}: ${x.outcome}\n${x.citations.map(citation).join('\n')}`).join('\n\n')}\n\n## Chronology\n${d.chronology.map(x => `${x.date}: ${x.event}\n${x.citations.map(citation).join('\n')}`).join('\n\n')}\n\n## Opposing evidence\n${statements(d.opposing_evidence)}\n\n## Counterargument\n${d.counterargument ? statements([d.counterargument]) : 'Unavailable'}\n\n## Falsification evidence\n${statements(d.falsification)}` : 'Research dossier unavailable.', ...bundle.notes].join('\n\n')
  const url = URL.createObjectURL(new Blob([format === 'json' ? JSON.stringify(payload, null, 2) : markdown], { type: format === 'json' ? 'application/json' : 'text/markdown' }))
  const a = document.createElement('a'); a.href = url; a.download = `research-report.${format}`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function InputRow({ entry, input, onEvidence, canOpen }: { entry: AuditEntry; input?: FindingInput; onEvidence: (id: string) => void; canOpen: boolean }) {
  const [open, setOpen] = useState(false)
  const outcomeClass = entry.effective_outcome === 'confirmed' ? 'ok' : entry.effective_outcome === 'contradicted' ? 'bad' : 'warn'
  return <>
    <tr className={entry.key ? 'sg-key' : ''}>
      <td><button className="sg-link" aria-expanded={open} onClick={() => setOpen(!open)}>{entry.input_name}</button>{entry.key && <span className="sg-tag">key input</span>}</td>
      <td className="sg-num">{input ? withUnit(input.value, input.unit) : '—'}</td>
      <td>{input ? `${label(input.basis)} · ${label(input.statement_status)}${input.as_of_date ? ` · ${input.as_of_date}` : ''}` : '—'}</td>
      <td><span className={`sg-pill ${outcomeClass}`}>{label(entry.effective_outcome)}{entry.conflict ? ' · conflict' : ''}</span></td>
      <td>{entry.effective_level === 'primary_source' ? 'Primary source' : 'Project text extraction only'}</td>
      <td className="sg-num">{entry.independent_confirming_groups}</td>
      <td>{label(entry.claim_extraction_status)} · {entry.claim_verification_status}</td>
    </tr>
    {open && <tr className="sg-detail"><td colSpan={7}>
      <p><b>Why:</b> {entry.reason}</p>
      {input && <Cite c={input.citation} onEvidence={onEvidence} canOpen={canOpen} />}
      <ul className="sg-results">{entry.results.map(r => <li key={r.verification_id}><code>{r.verification_id}</code> — {label(r.outcome)} at {label(r.level)} · {r.source}{r.page ? ` · PDF p.${r.page}` : ''}{safeSourceUrl(r.url) ? <> · <a href={safeSourceUrl(r.url)!} target="_blank" rel="noreferrer noopener">source document</a></> : ''} · passage SHA-256 <code>{r.passage_sha256}</code>
        {Object.keys(r.failed_or_open_checks).length > 0 && <> · open checks: {Object.entries(r.failed_or_open_checks).map(([k, v]) => `${label(k)} (${v})`).join(', ')}</>}</li>)}</ul>
      {entry.unavailable_sources.length > 0 && <p className="sg-warn-text">Unavailable sources: {JSON.stringify(entry.unavailable_sources)}</p>}
    </td></tr>}
  </>
}

export default function Signal({ bundle, error, evidenceIds, onEvidence }: { bundle: FindingBundle | null; error: string | null; evidenceIds: Set<string>; onEvidence: (id: string) => void }) {
  if (!bundle) return <section className="sg-empty" role="status"><h2>{error ? 'Finding not available' : 'Loading finding…'}</h2><p>{error ?? 'Reading the pipeline run.'}</p></section>
  const { finding: f, verifications, sourceManifest } = bundle
  const audit = f.audit_trail ?? []
  const byName = new Map(f.inputs.map(i => [i.name, i]))
  const auditNames = new Set(audit.map(a => a.input_name))
  const derived = f.inputs.filter(i => !auditNames.has(i.name))
  const primary = audit.filter(a => a.effective_level === 'primary_source').length
  const textOnly = audit.length - primary
  const confirmed = audit.filter(a => a.effective_outcome === 'confirmed').length
  const independent = audit.reduce((m, a) => Math.max(m, a.independent_confirming_groups), 0)
  const simulated = f.stage_provenance.filter(s => s.execution === 'simulated').map(s => s.stage)
  const crossChecks = verifications.flatMap(v => v.cross_checks.map(c => ({ ...c, input: v.input_name })))
  const renewableLocation = f.finding_id.endsWith('_H1_renewable_pipeline_location') &&
    f.company.name === 'NTPC Limited' && f.company.identity_status === 'registry_verified' && !f.synthetic &&
    f.finding_status === 'provisional_hypothesis' && !f.rejected_hypothesis
  const direct = (name: string) => {
    const matches = f.inputs.filter(i => i.name === name)
    return matches.length === 1 && matches[0].unit === 'MW' && Number.isFinite(matches[0].value) && matches[0].value > 0 ? matches[0].value : null
  }
  const parentTotal = direct('parent_under_implementation')
  const jvTotal = direct('jv_subsidiary_under_implementation')
  const parentReChecks = crossChecks.filter(c => c.expected_value === 725 && c.found_value === c.expected_value)
  const parentRe = parentReChecks.length === 1 ? parentReChecks[0].found_value : null
  const jvRe = direct('re_under_implementation_jv_subsidiary')
  const matchedDenominators = new Set(crossChecks.filter(c => c.input === 'total_under_implementation_group' && c.found_value !== null && c.found_value === c.expected_value).map(c => c.found_value))
  const groupRe = parentRe !== null && jvRe !== null ? parentRe + jvRe : null
  const validInputs = renewableLocation && parentRe !== null && parentTotal !== null && jvRe !== null && jvTotal !== null &&
    [parentRe, parentTotal, jvRe, jvTotal].every(v => Number.isFinite(v) && v > 0) &&
    parentTotal >= parentRe && jvTotal >= jvRe && matchedDenominators.has(parentTotal) && matchedDenominators.has(jvTotal) &&
    groupRe !== null && Number.isFinite(groupRe) && groupRe > 0
  const headlineShares = validInputs ? { parent: parentRe / groupRe * 100, jv: jvRe / groupRe * 100, total: groupRe } : null
  const showRenewableRatios = renewableLocation && !!headlineShares
  const showRenewableUnavailable = renewableLocation && !headlineShares
  const pct = (a: number, b: number) => `${(a / b * 100).toFixed(1)}%`
  const ratios = showRenewableRatios && groupRe !== null ? [
    { k: 'Parent renewable ÷ parent all-technology pipeline', n: parentRe!, d: parentTotal!, dn: 'Parent-owned pipeline, all technologies (table Total (I))' },
    { k: 'Renewable ÷ JV/subsidiary all-technology pipeline', n: jvRe!, d: jvTotal!, dn: 'Combined JV and subsidiary pipeline, all technologies (table Total (II))' },
    { k: 'JV/subsidiary renewable ÷ group renewable pipeline', n: jvRe!, d: groupRe, dn: 'Group renewable pipeline (sum of direct parent and JV/subsidiary renewable values)' },
    { k: 'Parent renewable ÷ group renewable pipeline', n: parentRe!, d: groupRe, dn: 'Group renewable pipeline (as above)' },
  ] : null
  const directParent = parentReChecks[0]
  const derivedResidual = renewableLocation ? derived.find(i => i.name === 'parent_re_under_implementation' && i.citation.locator?.startsWith('derived')) : undefined
  const tone = f.finding_status === 'supported_finding' ? 'good' : f.finding_status === 'provisional_hypothesis' ? 'caution' : 'stop'
  return <article className="sg">
    {f.synthetic && <div className="sg-banner bad" role="note"><b>SYNTHETIC EXAMPLE.</b> This run uses invented data and says nothing about any real company.</div>}
    <nav aria-label="Discovery walkthrough" className="sg-panel">
      <a href="#sg-question">Research question</a> · <a href="#sg-calc">Calculations</a> · <a href="#sg-ver">Evidence trail</a> · <a href="#sg-risk">Counterargument</a> · <a href="#sg-stage">Execution record</a>
    </nav>
    <header className={`sg-hero ${tone}`}>
      <div className="sg-eyebrow"><span className={`sg-status ${tone}`}>{STATUS[f.finding_status]}</span><span className="sg-strength">Evidence strength: <b>{f.evidence_strength}</b></span><span>{f.company.name}{f.periods.length ? ` · as of ${f.periods.join(', ')}` : ''}</span></div>
      <h2 className="sg-headline">{showRenewableRatios ? `Renewable pipeline: ${headlineShares!.parent.toFixed(1)}% parent-owned · ${headlineShares!.jv.toFixed(1)}% JV/subsidiary` : f.headline}</h2>
      {showRenewableRatios && <div className="sg-sub sg-renewable-comparison">
        <p>Share of total group renewable pipeline ({num(headlineShares!.total)} MW). Parent-owned {num(parentRe!)} / {num(headlineShares!.total)} MW = {pct(parentRe!, headlineShares!.total)}; JV/subsidiary {num(jvRe!)} / {num(headlineShares!.total)} MW = {pct(jvRe!, headlineShares!.total)}. JV/subsidiary pipeline capacity is not equivalent to the parent company’s economic ownership share.</p>
        <p><b>Original pipeline-run headline</b>: {f.headline} The original uses the rounded 14.5 GW figure and derived 709 MW residual.</p>
      </div>}
      {showRenewableUnavailable && <p role="status" className="sg-warn-text"><b>Recomputed renewable ratios unavailable.</b> Required direct MW values or matching denominator checks are missing or inconsistent; the stored headline is retained.</p>}
      <p className="sg-why">{f.why_it_matters}</p>
      {f.finding_status !== 'supported_finding' && <p className="sg-caveat"><b>{f.finding_status === 'provisional_hypothesis' ? 'Not a verified conclusion.' : 'Nothing is claimed here.'}</b> {f.finding_status === 'provisional_hypothesis' ? 'This is a hypothesis the evidence points toward but does not yet establish.' : 'The evidence available does not support a finding.'}</p>}
    </header>

    <div className="sg-downloads"><button onClick={() => downloadReport(bundle, 'json')}>Download report JSON</button><button onClick={() => downloadReport(bundle, 'md')}>Download report Markdown</button></div>
    {headlineShares && <details className="sg-panel"><summary>Headline numbers · formulas and source drilldown (2 decimals)</summary>
      <p>Parent: {parentRe!.toFixed(2)} ÷ {headlineShares.total.toFixed(2)} × 100 = {headlineShares.parent.toFixed(2)}%. JV/subsidiary: {jvRe!.toFixed(2)} ÷ {headlineShares.total.toFixed(2)} × 100 = {headlineShares.jv.toFixed(2)}%. Group renewable denominator = parent renewable + JV/subsidiary renewable.</p>
      <div className="sg-share-bar" role="img" aria-label={`Parent ${headlineShares.parent.toFixed(2)} percent; JV/subsidiary ${headlineShares.jv.toFixed(2)} percent`}><span style={{ width: `${headlineShares.parent}%` }} /><span style={{ width: `${headlineShares.jv}%` }} /></div>
      <p>Direct parent value cross-check: {directParent?.description}. These source checks do not resolve every attribution or period check.</p>
      {f.inputs.filter(x => ['re_under_implementation_group', 're_under_implementation_jv_subsidiary', 'parent_under_implementation', 'jv_subsidiary_under_implementation', 'total_under_implementation_group'].includes(x.name)).map(x => <div key={x.name}><b>{label(x.name)} · {x.value.toFixed(2)} {x.unit}</b><Cite c={x.citation} onEvidence={onEvidence} canOpen={!!x.citation.source_chunk_id && evidenceIds.has(x.citation.source_chunk_id)} /></div>)}
    </details>}
    <Dossier dossier={bundle.researchDossier} onEvidence={onEvidence} evidenceIds={evidenceIds} />

    <section aria-labelledby="sg-question" className="sg-panel">
      <h3 id="sg-question">Research question and reasoning</h3>
      <p>{renewableLocation ? 'Where does NTPC’s disclosed renewable project pipeline sit: in parent-owned projects or in joint ventures and subsidiaries?' : f.headline}</p>
      <p className="sg-sub">{bundle.researchDossier ? `Recorded chosen prompt: ${bundle.researchDossier.chosen_prompt}` : 'This question describes the saved investigation. The original assigned contest prompt has not been recorded in this bundle.'}</p>
      <ol>
        <li>Identify the reporting date, company boundary and project status for each input.</li>
        <li>Compare source passages with the extracted claims and preserve unresolved checks.</li>
        <li>Calculate shares using the stated numerator and denominator; distinguish rounded figures from direct table values.</li>
        <li>Assess competing explanations and reduce confidence when evidence remains incomplete.</li>
      </ol>
      <p>Current assessment: {STATUS[f.finding_status]} · {f.evidence_strength} evidence. The calculations describe disclosed project capacity; economic ownership and future commissioning require further evidence.</p>
    </section>

    <div className="sg-banner" role="note">
      <b>How this was verified.</b> {audit.length === 0 ? 'No verification audit is attached to this finding.' : <>{primary} of {audit.length} inputs were checked against a primary source{textOnly > 0 ? ` and ${textOnly} against the project’s own extracted text only` : ''}. {confirmed === audit.length ? 'All are confirmed.' : <b>Only {confirmed} of {audit.length} are fully confirmed; the rest are partially supported (open checks such as entity or period remain), so the inputs are not all confirmed.</b>}{independent === 0 ? ' No input is independently corroborated.' : ''}</>}
      {f.all_claims_unverified && <> The underlying extracted claims all remain <code>unverified</code>.</>}
      {simulated.length > 0 && <> <b>{simulated.join(' and ')} {simulated.length > 1 ? 'are' : 'is'} simulated:</b> a deterministic stand-in, not model output.</>}
    </div>

    {f.rejected_hypothesis && <div className="sg-banner bad"><b>Hypothesis rejected.</b> Key input(s) {f.rejected_hypothesis.failed_inputs.join(', ')} failed verification. The hypothesis was: “{f.rejected_hypothesis.headline_if_inputs_held}”.</div>}

    <section aria-labelledby="sg-calc"><h3 id="sg-calc">What was calculated</h3>
      <p className="sg-sub">{showRenewableRatios ? 'These are the original pipeline-run calculations and are preserved as reported. The parent renewable calculation uses the derived 709 MW residual and the group renewable calculation uses the rounded 14.5 GW; the headline above uses direct table values instead.' : 'Deterministic arithmetic on the inputs below. Ranges reflect rounding in the source figures.'}</p>
      <div className="sg-calcs">{f.calculations.map(c => <div className="sg-calc" key={c.calculation_id}>
        <div className="sg-calc-name">{label(c.name)}</div>
        {c.result ? <div className="sg-calc-value">{c.result.value.toFixed(2)}<small>{c.result.unit === 'percent' ? '%' : ` ${c.result.unit}`}</small></div> : <div className="sg-calc-value muted">not computed</div>}
        {c.result && c.result.lower_bound !== null && c.result.upper_bound !== null && <div className="sg-range">range {num(c.result.lower_bound, 1)}–{num(c.result.upper_bound, 1)}</div>}
        <div className="sg-formula">{c.formula}</div>
        <details><summary>Trace</summary><p>{c.trace}</p><p className="sg-inputs">Inputs: {c.input_names.map(label).join(' · ')}</p>{c.input_names.map(name => byName.get(name)).filter((x): x is FindingInput => !!x).map(x => <Cite key={x.name} c={x.citation} onEvidence={onEvidence} canOpen={!!x.citation.source_chunk_id && evidenceIds.has(x.citation.source_chunk_id)} />)}</details>
      </div>)}</div>
    </section>

    {derivedResidual && directParent && <section aria-labelledby="sg-dd" className="sg-panel"><h3 id="sg-dd">Derived value versus direct source value</h3>
      <div className="sg-two"><div><div className="sg-k">Derived residual</div><div className="sg-big">{withUnit(derivedResidual.value, derivedResidual.unit)}</div><p>{label(derivedResidual.name)}, obtained by subtracting two cited inputs. The original pipeline calculations retain this derived value.</p></div>
        <div><div className="sg-k">Direct table value</div><div className="sg-big">{num(directParent.found_value!)} MW</div><p>The matching source check confirms this directly reported renewable table value, which is used in the recomputed headline.</p></div></div>
    </section>}

    {ratios && <section aria-labelledby="sg-ratio" className="sg-panel"><h3 id="sg-ratio">Ratios and their denominators</h3>
      <p className="sg-sub">These four ratios answer different questions because they use different denominators and are not directly comparable. All use directly reported table values; none uses the derived 709 MW residual or rounded 14.5 GW. JV/subsidiary project pipeline capacity does not represent the parent company’s economic ownership share.</p>
      <div className="sg-scroll"><table className="sg-table sg-ratios"><thead><tr><th>Ratio</th><th>Numerator</th><th>Denominator</th><th>Value</th></tr></thead>
        <tbody>{ratios.map(r => <tr key={r.k}><td>{r.k}</td><td className="sg-num">{num(r.n)} MW</td><td>{num(r.d)} MW<br /><small>{r.dn}</small></td><td className="sg-num"><b>{pct(r.n, r.d)}</b></td></tr>)}</tbody></table></div>
    </section>}

    <section aria-labelledby="sg-ver"><h3 id="sg-ver">Inputs and verification</h3>
      {f.verification_summary && <p className="sg-sub">{f.verification_summary.key_inputs} key inputs · {f.verification_summary.confirmed_primary ?? 0} confirmed at primary source · {f.verification_summary.confirmed_text_only ?? 0} confirmed against project text only · {f.verification_summary.partial ?? 0} partially supported · {f.verification_summary.unresolved_or_unverifiable ?? 0} unresolved · {f.verification_summary.contradicted ?? 0} contradicted · {f.verification_summary.min_independent_groups ?? 0} independent source groups at the weakest key input</p>}
      {audit.length > 0 ? <div className="sg-scroll"><table className="sg-table"><thead><tr><th>Input</th><th>Value</th><th>Basis · status · date</th><th>Outcome</th><th>Verified against</th><th>Indep. groups</th><th>Claim state</th></tr></thead>
        <tbody>{audit.map(a => <InputRow key={a.role} entry={a} input={byName.get(a.input_name)} onEvidence={onEvidence} canOpen={!!byName.get(a.input_name)?.citation.source_chunk_id && evidenceIds.has(byName.get(a.input_name)!.citation.source_chunk_id!)} />)}</tbody></table></div>
        : <p className="sg-empty-note">No audit trail was attached to this finding.</p>}
      {derived.length > 0 && <div className="sg-derived"><b>Derived inputs</b> (computed from cited inputs, not read from a source): {derived.map(d => `${label(d.name)} = ${withUnit(d.value, d.unit)}`).join(' · ')}</div>}
      {(f.downgrade_reasons?.length ?? 0) > 0 && <div className="sg-panel"><h4>Why the finding is downgraded</h4><ul>{f.downgrade_reasons!.map(r => <li key={r}>{r}</li>)}</ul></div>}
    </section>

    <section aria-labelledby="sg-risk" className="sg-cols"><h3 id="sg-risk" className="sg-wide">Risks and what would change the conclusion</h3>
      <div><h4>Alternative explanations</h4><ul>{f.alternative_explanations.map(x => <li key={x}>{x}</li>)}</ul></div>
      <div><h4>Would falsify it</h4><ul>{f.falsification_conditions.map(x => <li key={x}>{x}</li>)}</ul></div>
      <div><h4>Missing evidence</h4><ul>{f.missing_evidence.map(x => <li key={x}>{x}</li>)}</ul></div>
      <div><h4>Limitations</h4><ul>{f.limitations.filter(x => !(primary > 0 && /all inputs are from the project.s own text extraction; none was checked against the original pdf/i.test(x))).map(x => <li key={x}>{x}</li>)}
        {primary > 0 && f.limitations.some(x => /all inputs are from the project.s own text extraction; none was checked against the original pdf/i.test(x)) && <li>Run-level verification checked {primary} of {audit.length} inputs at primary-source level; {textOnly} remained at project-text level. All reviewed inputs remain partially supported.</li>}
      </ul></div>
      {f.contradictory_evidence.length > 0 && <div className="sg-wide"><h4>Contradictory evidence</h4><ul>{f.contradictory_evidence.map(x => <li key={x.statement}>{x.statement}<Cite c={x.citation} onEvidence={onEvidence} canOpen={!!x.citation.source_chunk_id && evidenceIds.has(x.citation.source_chunk_id)} /></li>)}</ul></div>}
    </section>

    <section aria-labelledby="sg-stage"><h3 id="sg-stage">Pipeline provenance</h3>
      <ol className="sg-stages">{f.stage_provenance.map(s => <li key={s.stage} className={s.execution}><span className="sg-stage-name">{STAGE_NAMES[s.stage] ?? label(s.stage)}</span><span className={`sg-exec ${s.execution}`}>{EXEC[s.execution]}</span><span className="sg-stage-detail">{s.detail}</span></li>)}</ol>
      {bundle.catalogSources.length > 0 && <details className="sg-log"><summary>Source catalog availability ({bundle.catalogSources.length})</summary><ul>{bundle.catalogSources.map(source => <li key={source.source_id}><b>{source.title}</b> — {label(source.status)} · {source.publisher}{source.sha256 ? <> · PDF SHA-256 <code>{source.sha256}</code></> : ''}{safeSourceUrl(source.url) ? <> · <a href={safeSourceUrl(source.url)!} target="_blank" rel="noreferrer noopener">source URL</a></> : ''}</li>)}</ul><p>Catalog availability is not independent corroboration. Sources marked not retrieved were not used for verification.</p></details>}
    </section>

    {(f.decision_log?.length ?? 0) > 0 && <details className="sg-log"><summary>Decision log ({f.decision_log!.length})</summary><ul>{f.decision_log!.map(l => <li key={l}>{l}</li>)}</ul></details>}

    <footer className="sg-foot">
      <div>Finding <code>{f.finding_id}</code> · schema {f.schema_version} · rank score {f.rank_score} (provisional rubric, not calibrated{f.finding_status === 'provisional_hypothesis' ? '; provisional findings are capped below 50' : ''})</div>
      {sourceManifest ? <div>Source run <code>{sourceManifest.source_dir}</code> · {sourceManifest.files.map(x => `${x.name} ${x.sha256.slice(0, 8)}`).join(' · ')}</div> : <div>Run provenance unavailable (SOURCE.json missing).</div>}
      {bundle.notes.map(n => <div key={n} className="sg-warn-text">{n}</div>)}
    </footer>
  </article>
}
