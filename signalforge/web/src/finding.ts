// Typed parser for the backend finding contract (signalforge/schemas/finding.schema.json, schema_version 1.0) and its companion run files.
// The parser validates shape only; it never fills in missing values.
export type Execution = 'real' | 'simulated' | 'blocked' | 'not_executed'
export type Citation = { source_chunk_id: string | null; source_path: string | null; page: number | null; locator: string | null; excerpt: string; url: string | null }
export type FindingInput = {
  name: string; value: number; unit: string | null; as_of_date: string | null; basis: string | null; statement_status: string | null; claim_ids: string[]
  verification_ids: string[]; verification_outcome: string; verification_level: string; citation: Citation
}
export type CalcResult = { value: number; unit: string; lower_bound: number | null; upper_bound: number | null }
export type FindingCalculation = { calculation_id: string; name: string; formula: string; result: CalcResult | null; input_names: string[]; trace: string }
export type EvidenceItem = { statement: string; claim_ids: string[]; citation: Citation; independent: boolean }
export type AuditResult = { verification_id: string; level: string; outcome: string; source: string; page: number | null; url: string | null; passage_sha256: string; failed_or_open_checks: Record<string, string>; discrepancies: string[]; reviewer: string | null }
export type AuditEntry = {
  role: string; input_name: string; key: boolean; claim_id: string; claim_extraction_status: string; claim_verification_status: string; effective_outcome: string; effective_level: string
  conflict: boolean; reason: string; independent_confirming_groups: number; unavailable_sources: unknown[]; results: AuditResult[]
}
export type Stage = { stage: string; execution: Execution; detail: string }
export type Finding = {
  schema_version: '1.0'; finding_id: string; run_id: string; company: { name: string; aliases: string[]; identity_status: string }
  finding_status: 'supported_finding' | 'provisional_hypothesis' | 'no_defensible_signal'; evidence_strength: 'Strong' | 'Moderate' | 'Weak' | 'None'
  headline: string; why_it_matters: string; periods: string[]; rank_score: number; inputs: FindingInput[]; calculations: FindingCalculation[]
  supporting_evidence: EvidenceItem[]; contradictory_evidence: EvidenceItem[]; alternative_explanations: string[]; falsification_conditions: string[]
  missing_evidence: string[]; limitations: string[]; stage_provenance: Stage[]; all_claims_unverified: boolean; synthetic: boolean
  audit_trail?: AuditEntry[]; decision_log?: string[]; downgrade_reasons?: string[]; rejected_hypothesis?: { headline_if_inputs_held: string; failed_inputs: string[] } | null
  verification_summary?: Record<string, number>
}
export type CrossCheck = { description: string; expected_value: number; found_value: number | null; ok: boolean; independent: boolean }
export type VerificationResult = { verification_id: string; input_name: string; outcome: string; verification_level: string; cross_checks: CrossCheck[]; rationale: string }
export type SourceManifest = { source_run: string; source_dir: string; finding_id: string; files: { name: string; bytes: number; sha256: string }[] }
export type SourceCatalogEntry = { source_id: string; title: string; publisher: string; url: string; status: string; sha256: string | null; verification_level: string }
export type FindingBundle = { finding: Finding; verifications: VerificationResult[]; sourceManifest: SourceManifest | null; catalogSources: SourceCatalogEntry[]; notes: string[] }

const obj = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v)
const strs = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
const nstr = (v: unknown) => v === null || typeof v === 'string'
const isCitation = (v: unknown): v is Citation => obj(v) && typeof v.excerpt === 'string' && nstr(v.source_chunk_id) && nstr(v.source_path) && nstr(v.locator) && nstr(v.url) && (v.page === null || Number.isInteger(v.page))
const isInput = (v: unknown): v is FindingInput => obj(v) && typeof v.name === 'string' && typeof v.value === 'number' && nstr(v.unit) && nstr(v.as_of_date) && nstr(v.basis) && nstr(v.statement_status) && strs(v.claim_ids) && strs(v.verification_ids) && typeof v.verification_outcome === 'string' && typeof v.verification_level === 'string' && isCitation(v.citation)
const isCalc = (v: unknown): v is FindingCalculation => obj(v) && typeof v.name === 'string' && typeof v.formula === 'string' && typeof v.trace === 'string' && strs(v.input_names) && (v.result === null || (obj(v.result) && typeof v.result.value === 'number' && typeof v.result.unit === 'string'))
const isEvidence = (v: unknown): v is EvidenceItem => obj(v) && typeof v.statement === 'string' && strs(v.claim_ids) && isCitation(v.citation) && typeof v.independent === 'boolean'
const isStage = (v: unknown): v is Stage => obj(v) && typeof v.stage === 'string' && ['real', 'simulated', 'blocked', 'not_executed'].includes(v.execution) && typeof v.detail === 'string'
const isAudit = (v: unknown): v is AuditEntry => obj(v) && typeof v.input_name === 'string' && typeof v.key === 'boolean' && typeof v.effective_outcome === 'string' && typeof v.effective_level === 'string' && typeof v.conflict === 'boolean' && Number.isInteger(v.independent_confirming_groups) && Array.isArray(v.results) && typeof v.claim_id === 'string'

export function parseFinding(v: unknown): Finding | null {
  if (!obj(v) || v.schema_version !== '1.0') return null
  const ok = typeof v.finding_id === 'string' && typeof v.run_id === 'string' && obj(v.company) && typeof v.company.name === 'string'
    && ['supported_finding', 'provisional_hypothesis', 'no_defensible_signal'].includes(v.finding_status) && ['Strong', 'Moderate', 'Weak', 'None'].includes(v.evidence_strength)
    && typeof v.headline === 'string' && typeof v.why_it_matters === 'string' && typeof v.rank_score === 'number'
    && Array.isArray(v.inputs) && v.inputs.every(isInput) && Array.isArray(v.calculations) && v.calculations.every(isCalc)
    && Array.isArray(v.supporting_evidence) && v.supporting_evidence.every(isEvidence) && Array.isArray(v.contradictory_evidence) && v.contradictory_evidence.every(isEvidence)
    && strs(v.alternative_explanations) && strs(v.falsification_conditions) && strs(v.missing_evidence) && strs(v.limitations) && strs(v.periods)
    && Array.isArray(v.stage_provenance) && v.stage_provenance.every(isStage) && typeof v.all_claims_unverified === 'boolean' && typeof v.synthetic === 'boolean'
    && (v.audit_trail === undefined || (Array.isArray(v.audit_trail) && v.audit_trail.every(isAudit)))
    && (v.downgrade_reasons === undefined || strs(v.downgrade_reasons)) && (v.decision_log === undefined || strs(v.decision_log))
  return ok ? (v as unknown as Finding) : null
}
export function parseVerifications(v: unknown): VerificationResult[] {
  return Array.isArray(v) ? v.filter((r): r is VerificationResult => obj(r) && typeof r.verification_id === 'string' && typeof r.input_name === 'string' && Array.isArray(r.cross_checks) && typeof r.outcome === 'string') : []
}
export function parseSourceManifest(v: unknown): SourceManifest | null {
  return obj(v) && typeof v.source_run === 'string' && typeof v.finding_id === 'string' && Array.isArray(v.files) ? (v as unknown as SourceManifest) : null
}
export function parseSourceCatalog(v: unknown): SourceCatalogEntry[] {
  return Array.isArray(v) ? v.filter((s): s is SourceCatalogEntry => obj(s) && typeof s.source_id === 'string' && typeof s.title === 'string' && typeof s.publisher === 'string' && typeof s.url === 'string' && typeof s.status === 'string' && (s.sha256 === null || typeof s.sha256 === 'string') && typeof s.verification_level === 'string') : []
}
const base = () => ((import.meta as any).env?.BASE_URL ?? '/').replace(/\/?$/, '/') + 'data/finding/'
async function getJson(name: string): Promise<unknown> { const r = await fetch(base() + name); if (!r.ok) throw new Error(name); return r.json() }
/** Static, middleware-free loader: works in `vite dev`, `vite preview` and any static host. */
export async function loadFindingBundle(): Promise<FindingBundle | { error: string }> {
  try {
    const [rawFinding, rawVer, rawSrc, rawAudit] = await Promise.all([getJson('finding_bundle.json'), getJson('verification_results.json').catch(() => null), getJson('SOURCE.json').catch(() => null), getJson('audit_trail.json').catch(() => null)])
    const finding = parseFinding(rawFinding)
    if (!finding) return { error: 'finding_bundle.json does not match the finding contract (schema 1.0).' }
    const notes: string[] = []
    if (!finding.audit_trail && Array.isArray(rawAudit) && rawAudit.every(isAudit)) finding.audit_trail = rawAudit
    if (rawVer === null) notes.push('verification_results.json unavailable'); if (rawSrc === null) notes.push('SOURCE.json unavailable: run provenance cannot be shown')
    const sourceManifest = parseSourceManifest(rawSrc)
    const hasCatalogFile = sourceManifest?.files.some(f => f.name === 'source_catalog_status.json') ?? false
    const rawCatalog = hasCatalogFile ? await getJson('source_catalog_status.json').catch(() => null) : null
    if (hasCatalogFile && rawCatalog === null) notes.push('source_catalog_status.json unavailable')
    return { finding, verifications: parseVerifications(rawVer), sourceManifest, catalogSources: parseSourceCatalog(rawCatalog), notes }
  } catch { return { error: 'No finding bundle found. Run `npm run sync-data` in signalforge/web to copy a pipeline run into public/data/finding/.' } }
}
