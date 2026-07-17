import { describe, expect, it } from 'vitest'
import {
  clampMemberDraft,
  createMemberConversationState,
  projectMemberVisibleSummary,
  scriptedMemberTurn,
  switchMemberMode,
} from './memberDemo'

describe('member-safe conversation projection', () => {
  it('starts in Chat and preserves a single local session identity', () => {
    const state = createMemberConversationState()
    expect(state.mode).toBe('chat')
    expect(state.sessionId).toBe('member-demo-session')
  })

  it('preserves session context across modes and cancels simulated voice state on return to Chat', () => {
    const initial = createMemberConversationState()
    const withContext = { ...initial, draft: 'Keep this draft', voiceState: 'speaking' as const }
    const voice = switchMemberMode(withContext, 'voice')
    const chat = switchMemberMode(voice, 'chat')

    expect(voice.sessionId).toBe(initial.sessionId)
    expect(voice.events).toBe(initial.events)
    expect(voice.draft).toBe('Keep this draft')
    expect(chat.voiceState).toBe('idle')
    expect(chat.events).toBe(initial.events)
  })

  it('enforces the composer limit for paste-style input', () => {
    expect(clampMemberDraft('x'.repeat(4001))).toHaveLength(4000)
  })

  it('returns only authorization guidance when ROI is not permitted', () => {
    const result = projectMemberVisibleSummary('claim', false)
    const serialized = JSON.stringify(result)

    expect(result.kind).toBe('roi')
    expect(serialized).not.toContain('CLM')
    expect(serialized).not.toContain('MBR')
    expect(serialized).not.toContain('provider')
    expect(serialized).not.toContain('$')
  })

  it('renders ambiguity as explicit choices rather than silently selecting a service', () => {
    const events = scriptedMemberTurn('Is therapy covered?', 1)
    const resultEvent = events.find((event) => event.type === 'result')
    expect(resultEvent?.type === 'result' ? resultEvent.result.choices : undefined).toEqual([
      'Physical therapy evaluation',
      'Occupational therapy evaluation',
    ])
  })

  it('does not expose representative-only confidence or rule identifiers', () => {
    const result = projectMemberVisibleSummary('readiness')
    const serialized = JSON.stringify(result).toLowerCase()
    expect(serialized).not.toContain('confidence')
    expect(serialized).not.toContain('rule_id')
    expect(serialized).not.toContain('prior_auth_required')
  })
})
