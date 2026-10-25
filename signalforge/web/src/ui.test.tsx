// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LegacyApp as App } from './ui'

const evidence = {
  evidence_id: 'ev_0123456789abcdef01234567', company_name: 'NTPC Limited', verified_identifier: 'INE733E01010',
  company_identity_status: 'verified', source_organization: 'NSE', document_title: 'NTPC annual report extract',
  document_type: 'annual_report_text_extract', source_url: 'https://example.test/report.pdf', source_path: 'CSV/annual reports/report.csv',
  source_locator: 'page:12:block:3', source_identifier_status: 'repository_path_only', publication_date: '2025-05-10',
  event_date: '2025-03-31', retrieval_date: '2026-10-17', excerpt_or_fact: 'Illustrative test text; this is not a verified research claim.',
  metric_name: null, metric_value: null, unit: null, currency: null, reporting_period: 'FY 2024-25', evidence_category: 'unclassified',
  related_claim: null, claim_key: null, source_relationship: 'unknown', claim_verification_status: 'unverified',
  information_type: 'reported_fact', parsing_status: 'parsed', extraction_warnings: ['Test record remains under manual review.'],
  page_number: 12, table_identifier: null,
}
const claim = {
  schema_version: '1.0', claim_id: 'cl1_0123456789abcdef01234567', entity: 'NTPC Limited', entity_identity_status: 'verified',
  metric: 'installed capacity', raw_metric_text: 'installed capacity', value: 250, raw_value_text: '250', unit: 'MW', raw_unit_text: 'MW',
  period_type: 'financial_year', period_start: null, period_end: null, as_of_date: null, raw_period_text: 'FY 2024-25',
  source_document_id: 'doc_test', source_path: 'CSV/annual reports/2024-25.csv', source_page: 12,
  source_chunk_id: evidence.evidence_id, source_excerpt: 'TEST FIXTURE: installed capacity of 250 MW.',
  extraction_status: 'needs_review', ambiguity_notes: 'Test fixture only.', claim_verification_status: 'unverified', parser_version: 'test',
}
const audit = { dataset_filename: 'quotes.csv', audit_timestamp: '2026-10-16T00:00:00Z', row_count: 126, column_count: 14, column_names: ['DATE'], quality_warnings: [], limitations: ['No issuer identifier'] }
const readiness = { overall_readiness: 'not_ready', overall_rationale: 'Quote data has no operating evidence.', candidate_categories: [], f1_weights: { financial_significance: 30 } }

function mockOutputs(record = evidence, candidateClaims = [claim]) {
  const values: Record<string, string> = {
    audit: JSON.stringify(audit), readiness: JSON.stringify(readiness), companies: JSON.stringify({ companies: [{ canonical_name: 'NTPC Limited', verified_identifier: 'INE733E01010', aliases: ['NTPC'], verification_status: 'verified' }] }),
    ingestion: JSON.stringify({ document_count: 1, evidence_record_count: 1, verified_record_count: 1, unresolved_record_count: 0, metrics_extracted: 0, manual_review_evidence_ids_count: 1, generated_at: '2026-10-17T12:00:00Z' }),
    'claim-report': JSON.stringify({ run_status: 'completed', generated_at: '2026-10-17T18:25:24Z', input_record_count: 1, processed_chunk_count: 1, failed_chunk_count: 0, total_claims: candidateClaims.length, claims_by_status: { extracted: 0, ambiguous: 0, needs_review: candidateClaims.length }, claims_needing_attention: candidateClaims.length, schema_validation_failures: 0, review_queue_entries: candidateClaims.length, notes: ['All claims remain unverified.'] }),
    claims: candidateClaims.map(c => JSON.stringify(c)).join('\n'), f1: JSON.stringify({ error: 'No F1 output' }), r1: JSON.stringify({ error: 'No R1 output' }), evidence: JSON.stringify(record),
  }
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const key = String(input).split('/').pop() ?? ''
    return key in values ? new Response(values[key], { status: 200 }) : new Response('', { status: 404 })
  }))
}

async function renderApp() {
  const user = userEvent.setup(); render(<App />)
  await user.click(await screen.findByRole('button', { name: /^0\d\s?Overview/ }))
  return user
}

describe('SignalForge dashboard interactions', () => {
  beforeEach(() => { location.hash = ''; mockOutputs() })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('shows a blocked, non-discovery state when real F1 and R1 outputs are absent', async () => {
    await renderApp()
    expect(await screen.findByRole('heading', { name: /Evidence is assembled/ })).toBeTruthy()
    expect(screen.getByText(/not been reviewed and validated sufficiently for F1/)).toBeTruthy()
    expect(screen.getByText(/1 candidate needs attention/)).toBeTruthy()
  })

  it('opens a candidate claim through to its source record', async () => {
    const user = await renderApp()
    await user.click(await screen.findByRole('button', { name: /installed capacity 250 MW/ }))
    expect(await screen.findByText('EVIDENCE RECORD')).toBeTruthy()
    expect(screen.getByText('Test record remains under manual review.')).toBeTruthy()
    expect(screen.getByText(evidence.evidence_id)).toBeTruthy()
  })

  it('opens the evidence library source link safely and rejects unsafe protocols', async () => {
    const user = await renderApp()
    await user.click(await screen.findByRole('button', { name: /Evidence library/ }))
    await user.click(await screen.findByRole('button', { name: /NTPC annual report extract/ }))
    expect(await screen.findByText('EVIDENCE RECORD')).toBeTruthy()
    const link = screen.getByRole('link', { name: /Open source document/ })
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
    mockOutputs({ ...evidence, source_url: 'javascript:alert(1)' })
    cleanup(); location.hash = ''; render(<App />)
    await user.click(await screen.findByRole('button', { name: /Evidence library/ }))
    await user.click(await screen.findByRole('button', { name: /NTPC annual report extract/ }))
    expect(await screen.findByText('EVIDENCE RECORD')).toBeTruthy()
    expect(screen.queryByRole('link', { name: /Open source document/ })).toBeNull()
  })

  it('supports workspace navigation and evidence filtering', async () => {
    const user = await renderApp()
    await user.click(await screen.findByRole('button', { name: /Claim review/ }))
    expect(await screen.findByText(/candidate claims · all unverified/)).toBeTruthy()
    await user.type(screen.getByRole('textbox', { name: 'Search claims' }), 'no match')
    await waitFor(() => expect(screen.getByText('No claims match these filters.')).toBeTruthy())
    await user.click(screen.getByRole('button', { name: /Research angles/ }))
    expect(screen.getByRole('heading', { name: 'Research angles' })).toBeTruthy()
  })

  it('renders honest empty states for unavailable evidence and dates', async () => {
    mockOutputs(evidence, [])
    const user = await renderApp()
    expect(await screen.findByText('No candidate claims match this company.')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Claim review/ }))
    expect(await screen.findByText('No claims match these filters.')).toBeTruthy()
  })

  it('starts the backend run and keeps a blocked live result separate from the saved example', async () => {
    const user = await renderApp()
    const original = globalThis.fetch
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/agent/runs' && init?.method === 'POST') {
        return new Response(JSON.stringify({run_id:'research_20261024T180000_0123456789ab', company:'NTPC Limited', prompt:'Q', status:'blocked', stage:'machine_evidence', created_at:'2026-10-24T18:00:00Z', updated_at:'2026-10-24T18:00:00Z', events:[], artifacts:[]}), {status:202})
      }
      return original(input, init)
    })
    vi.stubGlobal('fetch', fetchMock)
    await user.type(screen.getByLabelText('Company', { selector: 'input' }), 'NTPC Limited')
    await user.click(await screen.findByRole('button', { name: /^Start research$/ }))
    expect(await screen.findByRole('heading', {name:/Current run.*Blocked at Machine Evidence/})).toBeTruthy()
    expect(screen.getByText(/has not produced a verified finding/)).toBeTruthy()
    expect(screen.getByText(/HISTORICAL SAVED WORKSPACE · NTPC Limited · Separate from live research above/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Historical saved pipeline stages' })).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === '/api/agent/runs' && init?.method === 'POST')).toBe(true)
  })
})
