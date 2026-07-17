import { describe, expect, it } from 'vitest'
import { createRepresentativeDemoState } from '@/lib/representativeDemo'
import { representativeReducer } from './representative-reducer'
import { loadRepresentativeDemoScenario } from '@/lib/representativeDemoRepository'

describe('representative interaction store', () => {
  it('provides injectable default, empty, slow, and error repository scenarios', async () => {
    const normal = await loadRepresentativeDemoScenario('default')
    const empty = await loadRepresentativeDemoScenario('empty')
    const slow = await loadRepresentativeDemoScenario('slow')

    expect(normal.waitingIds.length).toBeGreaterThan(0)
    expect(empty.waitingIds).toEqual([])
    expect(slow.waitingIds).toEqual(normal.waitingIds)
    await expect(loadRepresentativeDemoScenario('error')).rejects.toThrow(
      'Synthetic repository unavailable',
    )
  })

  it('always picks the oldest waiting interaction regardless of preview selection', () => {
    let state = createRepresentativeDemoState()
    state = representativeReducer(state, { type: 'select', id: 'int-ava' })
    state = representativeReducer(state, { type: 'pickup_next' })

    expect(state.activeIds).toEqual(['int-mia'])
    expect(state.waitingIds[0]).toBe('int-jordan')
    expect(state.selectedInteractionId).toBe('int-mia')
  })

  it('holds voice when selection moves away and never makes two voice interactions live', () => {
    let state = createRepresentativeDemoState()
    state = representativeReducer(state, { type: 'pickup_next' }) // Mia voice
    state = representativeReducer(state, { type: 'pickup_next' }) // Jordan chat
    state = representativeReducer(state, { type: 'pickup_next' }) // Priya voice

    expect(state.records['int-mia'].voiceState).toBe('held')
    expect(state.records['int-priya'].voiceState).toBe('live')
    expect(
      Object.values(state.records).filter((record) => record.voiceState === 'live'),
    ).toHaveLength(1)

    state = representativeReducer(state, { type: 'select', id: 'int-mia' })
    expect(state.records['int-mia'].voiceState).toBe('held')
    expect(state.records['int-priya'].voiceState).toBe('held')

    state = representativeReducer(state, { type: 'resume_voice', id: 'int-mia' })
    expect(state.records['int-mia'].voiceState).toBe('live')
    expect(state.records['int-priya'].voiceState).toBe('held')
  })

  it('hides and reopens tabs without completing the interaction', () => {
    let state = createRepresentativeDemoState()
    state = representativeReducer(state, { type: 'pickup_next' })
    state = representativeReducer(state, { type: 'hide_tab', id: 'int-mia' })

    expect(state.activeIds).toContain('int-mia')
    expect(state.completedIds).not.toContain('int-mia')
    expect(state.openTabIds).not.toContain('int-mia')

    state = representativeReducer(state, { type: 'reopen_tab', id: 'int-mia' })
    expect(state.openTabIds).toContain('int-mia')
    expect(state.selectedInteractionId).toBe('int-mia')
  })

  it('records a required disposition when completing an interaction', () => {
    let state = createRepresentativeDemoState()
    state = representativeReducer(state, { type: 'pickup_next' })
    state = representativeReducer(state, {
      type: 'complete',
      id: 'int-mia',
      disposition: 'Follow-up required',
    })

    expect(state.activeIds).not.toContain('int-mia')
    expect(state.completedIds[0]).toBe('int-mia')
    expect(state.records['int-mia'].disposition).toBe('Follow-up required')
  })

  it('increments unread chat messages only for inactive interactions', () => {
    let state = createRepresentativeDemoState()
    state = representativeReducer(state, { type: 'pickup_next' })
    state = representativeReducer(state, { type: 'pickup_next' })
    state = representativeReducer(state, { type: 'select', id: 'int-mia' })
    state = representativeReducer(state, { type: 'incoming_message', id: 'int-jordan' })

    expect(state.records['int-jordan'].unreadCount).toBe(1)
    state = representativeReducer(state, { type: 'select', id: 'int-jordan' })
    expect(state.records['int-jordan'].unreadCount).toBe(0)
  })
})
