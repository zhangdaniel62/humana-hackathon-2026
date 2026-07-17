import { describe, expect, it } from 'vitest'
import { projectSessionSummary, summaryApiPath } from './conversationSummary'

describe('conversation summary projection', () => {
  it('accepts an incomplete summary and projects only present dictionary findings', () => {
    const summary = projectSessionSummary({
      session_id: 'session-1',
      status: 'incomplete',
      roi: { status: 'verified', message: 'Authorization is verified.', reason: 'Caller matched.' },
      claim: null,
      benefits: {
        status: 'ok',
        answer_text: 'The service is covered.',
        covered: true,
        prior_auth_required: false,
        made_up_client_fallback: 'must not render',
      },
      readiness: null,
      notification_preview: null,
      missing_findings: ['claim', 'readiness'],
    })

    expect(summary?.status).toBe('incomplete')
    expect(summary?.missingFindings).toEqual(['claim', 'readiness'])
    expect(summary?.sections.map((section) => section.key)).toEqual(['roi', 'benefits'])
    expect(JSON.stringify(summary)).not.toContain('made_up_client_fallback')
    expect(JSON.stringify(summary)).not.toContain('Claim information is available')
  })

  it('ignores malformed finding dictionaries without rejecting a valid envelope', () => {
    const summary = projectSessionSummary({
      session_id: 'session-2',
      status: 'ready',
      roi: 'not-a-dict',
      claim: [],
      benefits: null,
      readiness: { status: 'incomplete', message: 'More claim fields are required.' },
      notification_preview: null,
      missing_findings: [],
    })
    expect(summary?.sections).toHaveLength(1)
    expect(summary?.sections[0]?.summary).toBe('More claim fields are required.')
  })

  it('accepts only API paths returned by the backend summary contract', () => {
    expect(summaryApiPath('/api/sessions/session-1/summary')).toBe('/api/sessions/session-1/summary')
    expect(summaryApiPath('https://example.test/api/sessions/session-1/summary')).toBeNull()
  })
})
