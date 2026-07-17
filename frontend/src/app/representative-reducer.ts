import {
  createRepresentativeDemoState,
  type InteractionDisposition,
  type InteractionSection,
  type RepresentativeDemoState,
  type RepresentativeInteraction,
} from '@/lib/representativeDemo'

export type RepresentativeAction =
  | { type: 'hydrate'; state: RepresentativeDemoState }
  | { type: 'pickup_next' }
  | { type: 'select'; id: string }
  | { type: 'hide_tab'; id: string }
  | { type: 'reopen_tab'; id: string }
  | { type: 'resume_voice'; id: string }
  | { type: 'toggle_mute'; id: string }
  | { type: 'set_section'; id: string; section: InteractionSection }
  | { type: 'set_draft'; id: string; draft: string }
  | { type: 'send_message'; id: string }
  | { type: 'incoming_message'; id: string }
  | { type: 'complete'; id: string; disposition: InteractionDisposition }
  | { type: 'reset' }

function updateRecord(
  state: RepresentativeDemoState,
  id: string,
  update: (record: RepresentativeInteraction) => RepresentativeInteraction,
): RepresentativeDemoState {
  const current = state.records[id]
  if (!current) return state
  return { ...state, records: { ...state.records, [id]: update(current) } }
}

function holdLiveVoiceExcept(
  records: Record<string, RepresentativeInteraction>,
  exceptId: string,
): Record<string, RepresentativeInteraction> {
  return Object.fromEntries(
    Object.entries(records).map(([id, record]) => [
      id,
      id !== exceptId && record.channel === 'voice' && record.voiceState === 'live'
        ? { ...record, voiceState: 'held' as const }
        : record,
    ]),
  )
}

export function representativeReducer(
  state: RepresentativeDemoState,
  action: RepresentativeAction,
): RepresentativeDemoState {
  switch (action.type) {
    case 'hydrate':
      return action.state
    case 'pickup_next': {
      const id = state.waitingIds[0]
      if (!id) return state
      const picked = state.records[id]
      const records = holdLiveVoiceExcept(state.records, id)
      records[id] = {
        ...picked,
        phase: 'active',
        pickedUpAt: 'Now',
        tabOpen: true,
        voiceState: picked.channel === 'voice' ? 'live' : null,
        unreadCount: 0,
      }
      return {
        ...state,
        records,
        waitingIds: state.waitingIds.slice(1),
        activeIds: [...state.activeIds, id],
        openTabIds: [...state.openTabIds, id],
        selectedInteractionId: id,
      }
    }
    case 'select': {
      const selected = state.records[action.id]
      if (!selected || !state.activeIds.includes(action.id)) return state
      let records = holdLiveVoiceExcept(state.records, action.id)
      records = { ...records, [action.id]: { ...selected, unreadCount: 0 } }
      return { ...state, records, selectedInteractionId: action.id }
    }
    case 'hide_tab': {
      if (!state.openTabIds.includes(action.id)) return state
      const openTabIds = state.openTabIds.filter((id) => id !== action.id)
      const hiddenIndex = state.openTabIds.indexOf(action.id)
      const neighbor = openTabIds[hiddenIndex] ?? openTabIds[hiddenIndex - 1] ?? null
      const next = updateRecord(state, action.id, (record) => ({ ...record, tabOpen: false }))
      return {
        ...next,
        openTabIds,
        selectedInteractionId:
          state.selectedInteractionId === action.id ? neighbor : state.selectedInteractionId,
      }
    }
    case 'reopen_tab': {
      if (!state.activeIds.includes(action.id) || state.openTabIds.includes(action.id)) return state
      const next = updateRecord(state, action.id, (record) => ({
        ...record,
        tabOpen: true,
        unreadCount: 0,
      }))
      return {
        ...next,
        openTabIds: [...state.openTabIds, action.id],
        selectedInteractionId: action.id,
      }
    }
    case 'resume_voice': {
      const record = state.records[action.id]
      if (!record || record.channel !== 'voice' || record.phase !== 'active') return state
      const records = holdLiveVoiceExcept(state.records, action.id)
      records[action.id] = { ...record, voiceState: 'live' }
      return { ...state, records, selectedInteractionId: action.id }
    }
    case 'toggle_mute':
      return updateRecord(state, action.id, (record) => {
        if (record.channel !== 'voice' || record.voiceState === 'held') return record
        return { ...record, voiceState: record.voiceState === 'muted' ? 'live' : 'muted' }
      })
    case 'set_section':
      return updateRecord(state, action.id, (record) => ({
        ...record,
        selectedSection: action.section,
      }))
    case 'set_draft':
      return updateRecord(state, action.id, (record) => ({ ...record, draft: action.draft }))
    case 'send_message':
      return updateRecord(state, action.id, (record) => {
        const text = record.draft.trim()
        if (!text || record.channel !== 'chat') return record
        return {
          ...record,
          draft: '',
          transcript: [
            ...record.transcript,
            {
              id: `${record.id}-rep-${record.transcript.length}`,
              speaker: 'representative',
              speakerLabel: 'Representative',
              text,
              timestamp: 'Now',
            },
          ],
        }
      })
    case 'incoming_message':
      return updateRecord(state, action.id, (record) => ({
        ...record,
        unreadCount:
          state.selectedInteractionId === action.id ? record.unreadCount : record.unreadCount + 1,
        transcript: [
          ...record.transcript,
          {
            id: `${record.id}-member-${record.transcript.length}`,
            speaker: 'member',
            speakerLabel: record.memberLabel,
            text: 'I have one more question before we finish.',
            timestamp: 'Now',
          },
        ],
      }))
    case 'complete': {
      const record = state.records[action.id]
      if (!record || record.phase !== 'active') return state
      const activeIds = state.activeIds.filter((id) => id !== action.id)
      const openTabIds = state.openTabIds.filter((id) => id !== action.id)
      const closedIndex = state.openTabIds.indexOf(action.id)
      const neighbor = openTabIds[closedIndex] ?? openTabIds[closedIndex - 1] ?? null
      const records = {
        ...state.records,
        [action.id]: {
          ...record,
          phase: 'completed' as const,
          status: action.disposition === 'Resolved' ? ('success' as const) : ('neutral' as const),
          completedAt: 'Now',
          durationLabel: '12 min',
          disposition: action.disposition,
          resolutionSummary:
            action.disposition === 'Resolved'
              ? 'The representative confirmed the grounded next step with the member.'
              : `Interaction closed as ${action.disposition.toLowerCase()}.`,
          voiceState: null,
          tabOpen: false,
        },
      }
      return {
        ...state,
        records,
        activeIds,
        openTabIds,
        completedIds: [action.id, ...state.completedIds],
        selectedInteractionId:
          state.selectedInteractionId === action.id ? neighbor : state.selectedInteractionId,
      }
    }
    case 'reset':
      return createRepresentativeDemoState()
  }
}
