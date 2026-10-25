import type { Investigation } from './investigation'

// Contract of signalforge/research_service.py + research_session.py (manifest.json).
export type RunStage = { name: string; execution: string; detail?: string }
export type LiveRun = {
  run_id: string; company: string; prompt: string; status: string; stage: string
  created_at: string; updated_at?: string; finished_at?: string
  model?: { provider: string; model: string }
  stages?: RunStage[]
  events: { at: string; stage: string; message: string }[]
  artifacts: string[]
  discovery_actions?: { action: string; at: string; url?: string; query?: string }[]
  error?: { type?: string; frames?: string[]; provider_detail?: string } | null
  f1_ranking_provenance?: unknown
  investigation?: Investigation | null
}
export type RunSummary = Pick<LiveRun, 'run_id' | 'company' | 'prompt' | 'created_at' | 'status' | 'stage'>

export const RUN_ID = /^research_\d{8}T\d{6}_[a-f0-9]{12}$/
export const ACTIVE = new Set(['queued', 'running'])
export const TERMINAL = new Set(['completed', 'blocked', 'failed'])
export const POLL_MS = 3000          // local model inference is slow; do not hammer the service
export const MAX_POLL_FAILURES = 5
export const REQUEST_TIMEOUT_MS = 15000
export const SERVICE_HINT = 'Start it with PYTHONPATH=signalforge/src python3 -m signalforge.research_service from the repository root.'

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) { super(message) }
}

export async function api<T>(url: string, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const outer = init.signal
  const onAbort = () => controller.abort()
  outer?.addEventListener('abort', onAbort)
  try {
    let response: Response
    try { response = await fetch(url, { ...init, signal: controller.signal }) }
    catch {
      if (outer?.aborted) throw new ApiError('aborted')
      throw new ApiError(controller.signal.aborted ? `Research service did not answer within ${timeoutMs / 1000} seconds.` : `Local research service unavailable. ${SERVICE_HINT}`)
    }
    let body: unknown = null
    try { body = await response.json() } catch { /* non-JSON error page */ }
    if (!response.ok) {
      const message = body && typeof body === 'object' && 'error' in body ? String((body as { error: unknown }).error) : `HTTP ${response.status}`
      throw new ApiError(message, response.status)
    }
    if (body === null) throw new ApiError('Research service returned an unreadable response.', response.status)
    return body as T
  } finally { clearTimeout(timer); outer?.removeEventListener('abort', onAbort) }
}

export const startRun = (company: string, prompt: string, signal?: AbortSignal) =>
  api<LiveRun>('/api/agent/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ company, prompt }), signal })
export const getRun = (id: string, signal?: AbortSignal) => api<LiveRun>(`/api/agent/runs/${encodeURIComponent(id)}`, { signal })
export const listRuns = (signal?: AbortSignal) => api<{ runs: RunSummary[] }>('/api/agent/runs', { signal })

export function isLiveRun(value: unknown): value is LiveRun {
  const v = value as LiveRun
  return !!v && typeof v === 'object' && typeof v.run_id === 'string' && typeof v.status === 'string' && typeof v.company === 'string'
}

const words = (s?: string | null) => (s || 'unknown').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())

const STAGE_LABELS: Record<string, string> = {
  real: 'Executed', running: 'Running', not_executed: 'Not executed', blocked: 'Blocked', failed: 'Failed',
  completed: 'Completed', deterministic_evidence_gap: 'Evidence gap (no model review)',
}
export const stageLabel = (execution: string) => STAGE_LABELS[execution] ?? words(execution)
export const stageTone = (execution: string) =>
  execution === 'real' || execution === 'completed' ? 'done' : execution === 'running' ? 'running'
    : execution === 'blocked' || execution === 'failed' ? 'blocked' : 'unknown'

/** Honest one-line outcome; acceptance (202/queued) is never shown as success. */
export function outcome(run: LiveRun): { label: string; tone: string } {
  const gap = run.investigation?.report_type === 'evidence_gap'
  if (run.status === 'queued') return { label: 'Queued · not started yet', tone: 'running' }
  if (run.status === 'running') return { label: `Running · ${words(run.stage)}`, tone: 'running' }
  if (run.status === 'completed' && gap) return { label: 'Finished · evidence-gap report, no verified finding', tone: 'review' }
  if (run.status === 'completed' && run.investigation) return { label: `Finished · investigation ${run.investigation.status}`, tone: 'done' }
  if (run.status === 'completed') return { label: 'Finished without a final investigation report', tone: 'review' }
  if (run.status === 'blocked') return { label: `Blocked at ${words(run.stage)}`, tone: 'blocked' }
  if (run.status === 'failed') return { label: `Failed at ${words(run.stage)}`, tone: 'blocked' }
  return { label: `Unrecognised status "${run.status}"`, tone: 'unknown' }
}

/** Old or partial manifests may omit fields; never crash or invent content. */
export function normalizeInvestigation(i: Investigation): Investigation {
  const list = <T,>(x: T[] | undefined | null) => Array.isArray(x) ? x : []
  return {
    ...i,
    headline: i.headline || 'Untitled investigation', summary: i.summary || 'Summary unavailable.',
    why_it_matters: list(i.why_it_matters), claims: list(i.claims), sources: list(i.sources).map(s => ({ ...s, passages: list(s.passages) })),
    timeline: list(i.timeline), calculations: list(i.calculations), strength_reasons: list(i.strength_reasons),
    limitations: list(i.limitations), decision_log: list(i.decision_log), research_leads: list(i.research_leads),
    counterargument: { text: i.counterargument?.text ?? '', evidence_ids: list(i.counterargument?.evidence_ids) },
    falsification: i.falsification ?? '', evidence_strength: i.evidence_strength ?? 'Weak', completed_at: i.completed_at ?? 'unavailable',
  }
}

/** A report belongs to a run only if it names that run (or names nothing). */
export function reportMismatch(run: LiveRun): string | null {
  const i = run.investigation
  if (!i) return null
  if (i.run_id && i.run_id !== run.run_id) return `report run ${i.run_id} differs from run ${run.run_id}`
  if (i.company && i.company.trim().toLowerCase() !== run.company.trim().toLowerCase()) return `report company "${i.company}" differs from run company "${run.company}"`
  return null
}
