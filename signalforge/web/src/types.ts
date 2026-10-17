export type Audit = {
  dataset_filename: string; audit_timestamp: string; row_count: number; column_count: number;
  column_names: string[]; date_coverage?: Record<string, { start: string; end: string }>;
  company_identifier_columns?: string[]; quality_warnings: string[]; limitations: string[];
}
export type ReadinessCategory = {
  category: 'renewable_transition' | 'capacity_conversion' | 'hidden_relationships';
  evidence_missing: string[]; relevant_metrics_calculable: unknown[]; readiness_rating: string;
  readiness_rationale: string; recommended_next_action: string;
}
export type Readiness = { overall_readiness: string; overall_rationale: string; candidate_categories: ReadinessCategory[]; f1_weights: Record<string, number> }
export type Evidence = {
  evidence_id: string; company_name?: string | null; company_identity_status?: 'verified' | 'unresolved';
  source_organization?: string | null; document_title: string; document_type?: string; source_url?: string | null;
  source_path?: string | null; source_locator?: string; publication_date?: string | null; event_date?: string | null;
  excerpt_or_fact: string; metric_name?: string | null; metric_value?: string | number | null; unit?: string | null;
  currency?: string | null; reporting_period?: string | null; evidence_category?: string; related_claim?: string | null;
  source_relationship?: string; claim_verification_status?: string; information_type?: string; retrieval_date?: string | null;
  parsing_status?: string; extraction_warnings?: string[]; page_number?: number | null; table_identifier?: string | null;
}
export type Claim = {
  claim_id: string; entity?: string | null; entity_identity_status: 'verified' | 'unresolved'; metric?: string | null;
  raw_metric_text?: string | null; value: number | null; raw_value_text: string; unit?: string | null; raw_unit_text: string;
  period_type: string; period_start?: string | null; period_end?: string | null; as_of_date?: string | null;
  raw_period_text?: string | null; source_document_id: string; source_path: string; source_page?: number | null;
  source_chunk_id: string; source_excerpt: string; extraction_status: 'extracted' | 'ambiguous' | 'needs_review';
  ambiguity_notes?: string | null; claim_verification_status: 'unverified';
}
export type ClaimReport = {
  run_status: string; generated_at: string; input_record_count: number; processed_chunk_count: number;
  failed_chunk_count: number; total_claims: number; claims_by_status: Record<string, number>;
  claims_needing_attention: number; schema_validation_failures: number; review_queue_entries: number;
  notes: string[];
}
export type Company = { canonical_name: string; verified_identifier: string; aliases?: string[]; verification_status: string }
export type F1 = { company_name: string; ranking_reliable: boolean; ranking_limitation: string | null; ranked_candidates: Array<{ candidate_id: string; rank: number; category: string; hypothesis: string; financial_importance: string; scores: Record<string, {score:number; rationale:string}>; weighted_score: number; evidence_found: Array<{evidence_id:string|null; status:string; statement:string}>; alternative_explanation: string; falsification_condition: string }>; recommended_candidate_id: string | null }
export type R1 = { hypothesis: string; alternative_explanation: string; falsification_test: string; retrieval_performed: false }
export type ResearchData = { audit: Audit | null; readiness: Readiness | null; evidence: Evidence[]; ingestion: Record<string, unknown> | null; f1: F1 | null; r1: R1 | null; companies: Company[]; claims: Claim[]; claimReport: ClaimReport | null; unavailable: string[] }

const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
export const isAudit = (v: unknown): v is Audit => obj(v) && typeof v.dataset_filename === 'string' && Number.isInteger(v.row_count) && Array.isArray(v.column_names) && Array.isArray(v.limitations)
export const isReadiness = (v: unknown): v is Readiness => obj(v) && typeof v.overall_readiness === 'string' && Array.isArray(v.candidate_categories) && obj(v.f1_weights)
export const isClaimReport = (v: unknown): v is ClaimReport => obj(v) && typeof v.run_status === 'string' && Number.isInteger(v.total_claims) && obj(v.claims_by_status) && Number.isInteger(v.claims_needing_attention)
export const isCompanyList = (v: unknown): v is { companies: Company[] } => obj(v) && Array.isArray(v.companies) && v.companies.every(c => obj(c) && typeof c.canonical_name === 'string' && c.verification_status === 'verified')
export const parseEvidenceNdjson = (raw: string): Evidence[] => raw.split(/\r?\n/).filter(Boolean).flatMap(line => {
  try { const v: unknown = JSON.parse(line); return obj(v) && typeof v.evidence_id === 'string' && typeof v.document_title === 'string' && typeof v.excerpt_or_fact === 'string' ? [v as Evidence] : [] } catch { return [] }
})
export const parseClaimsNdjson = (raw: string): Claim[] => raw.split(/\r?\n/).filter(Boolean).flatMap(line => {
  try {
    const v: unknown = JSON.parse(line)
    return obj(v) && typeof v.claim_id === 'string' && typeof v.source_path === 'string' && typeof v.source_chunk_id === 'string' && typeof v.source_excerpt === 'string' && typeof v.raw_value_text === 'string' && ['extracted', 'ambiguous', 'needs_review'].includes(String(v.extraction_status)) && v.claim_verification_status === 'unverified' ? [v as unknown as Claim] : []
  } catch { return [] }
})
async function jsonResource<T>(name: string, validate: (v: unknown) => v is T, unavailable: string[]): Promise<T | null> {
  try { const response = await fetch(`/api/research/${name}`); if (!response.ok) throw new Error(); const value: unknown = await response.json(); if (!validate(value)) throw new Error(); return value }
  catch { unavailable.push(name); return null }
}
export async function loadResearchData(): Promise<ResearchData> {
  const unavailable: string[] = []
  const [audit, readiness, ingestion, f1, r1, claimReport, companyRegistry, evidenceResponse, claimResponse] = await Promise.all([
    jsonResource('audit', isAudit, unavailable), jsonResource('readiness', isReadiness, unavailable),
    jsonResource('ingestion', obj, unavailable), jsonResource('f1', obj, unavailable), jsonResource('r1', obj, unavailable),
    jsonResource('claim-report', isClaimReport, unavailable), jsonResource('companies', isCompanyList, unavailable),
    fetch('/api/research/evidence').catch(() => null),
    fetch('/api/research/claims').catch(() => null),
  ])
  let evidence: Evidence[] = []
  if (evidenceResponse?.ok) { try { evidence = parseEvidenceNdjson(await evidenceResponse.text()) } catch { unavailable.push('evidence') } }
  else unavailable.push('evidence')
  let claims: Claim[] = []
  if (claimResponse?.ok) { try { claims = parseClaimsNdjson(await claimResponse.text()) } catch { unavailable.push('claims') } }
  else unavailable.push('claims')
  return { audit, readiness, evidence, ingestion, f1: f1 && 'company_name' in f1 && Array.isArray(f1.ranked_candidates) ? f1 as unknown as F1 : null, r1: r1 && 'hypothesis' in r1 ? r1 as unknown as R1 : null, companies: companyRegistry?.companies ?? [], claims, claimReport, unavailable: [...new Set(unavailable)] }
}

export const categoryLabels: Record<ReadinessCategory['category'], string> = {
  renewable_transition: 'Renewable transition', capacity_conversion: 'Announced → commissioned', hidden_relationships: 'Hidden relationships',
}
export function safeSourceUrl(value?: string | null): string | null {
  if (!value) return null
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null } catch { return null }
}
