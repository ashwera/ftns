import { describe, expect, it } from 'vitest'
import { isAudit, isReadiness, parseEvidenceNdjson, safeSourceUrl } from './types'

describe('backend output adapters', () => {
  it('accepts the current dataset audit shape and rejects incomplete data', () => {
    expect(isAudit({ dataset_filename: 'quotes.csv', row_count: 126, column_names: ['DATE'], limitations: [] })).toBe(true)
    expect(isAudit({ dataset_filename: 'quotes.csv', row_count: '126', column_names: ['DATE'] })).toBe(false)
  })
  it('accepts the current readiness structure without inventing F1 output', () => {
    expect(isReadiness({ overall_readiness: 'not_ready', candidate_categories: [], f1_weights: { financial_significance: 30 } })).toBe(true)
    expect(isReadiness({ overall_readiness: 'not_ready', candidate_categories: [] })).toBe(false)
  })
  it('keeps valid evidence, skips malformed and incomplete JSONL records', () => {
    const records = parseEvidenceNdjson([
      '{"evidence_id":"ev_abc","document_title":"Annual report","excerpt_or_fact":"Requires review","source_path":"reports/ar.csv"}',
      '{bad json}',
      '{"evidence_id":"ev_missing_excerpt","document_title":"Incomplete"}',
    ].join('\n'))
    expect(records).toHaveLength(1)
    expect(records[0].source_path).toBe('reports/ar.csv')
  })
  it('handles an empty evidence store', () => { expect(parseEvidenceNdjson('')).toEqual([]) })
  it('allows only HTTP(S) source URLs', () => {
    expect(safeSourceUrl('https://example.test/source')).toBe('https://example.test/source')
    expect(safeSourceUrl('javascript:alert(1)')).toBeNull()
    expect(safeSourceUrl('not a URL')).toBeNull()
  })
})
