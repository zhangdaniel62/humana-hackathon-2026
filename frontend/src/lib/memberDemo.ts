import type { StatusVariant } from '@/components/ui'
import type { TranscriptMessage } from './representativeDemo'

export type MemberMode = 'chat' | 'voice'
export type MemberVoiceState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface MemberVisibleSummary {
  id: string
  kind: 'claim_story' | 'benefits' | 'readiness' | 'notification' | 'escalation' | 'roi'
  title: string
  summary: string
  tone: StatusVariant
  badge?: string
  details: Array<{ label: string; value: string }>
  source?: string
  choices?: string[]
}

export type MemberConversationEvent =
  | { id: string; type: 'message'; message: TranscriptMessage }
  | { id: string; type: 'result'; result: MemberVisibleSummary }

export interface MemberConversationState {
  sessionId: string
  mode: MemberMode
  voiceState: MemberVoiceState
  draft: string
  events: MemberConversationEvent[]
}

export function clampMemberDraft(value: string): string {
  return value.slice(0, 4000)
}

export function switchMemberMode(
  state: MemberConversationState,
  mode: MemberMode,
): MemberConversationState {
  return {
    ...state,
    mode,
    voiceState: mode === 'chat' ? 'idle' : state.voiceState,
  }
}

type ScriptedScenario = 'claim' | 'benefits' | 'readiness' | 'roi' | 'ambiguity' | 'escalation'

const source = 'Synthetic Claim Assist demonstration data'

function assistantMessage(id: string, text: string): MemberConversationEvent {
  return {
    id,
    type: 'message',
    message: {
      id,
      speaker: 'assistant',
      speakerLabel: 'Claim Assist',
      text,
      timestamp: 'Now',
    },
  }
}

export function createMemberConversationState(): MemberConversationState {
  return {
    sessionId: 'member-demo-session',
    mode: 'chat',
    voiceState: 'idle',
    draft: '',
    events: [
      assistantMessage(
        'member-greeting',
        'Hi — I can help explain a claim, check coverage, or help you understand a denial using synthetic demo information.',
      ),
    ],
  }
}

export function projectMemberVisibleSummary(
  scenario: ScriptedScenario,
  roiPermitted = true,
): MemberVisibleSummary {
  if (!roiPermitted || scenario === 'roi') {
    return {
      id: 'member-result-roi',
      kind: 'roi',
      title: 'Authorization required',
      summary:
        'I cannot share another adult member’s information until Release of Information authorization is verified.',
      tone: 'danger',
      badge: 'Restricted',
      details: [
        {
          label: 'Next step',
          value: 'Ask the member to submit or update authorization before requesting claim details.',
        },
      ],
    }
  }

  const summaries: Record<Exclude<ScriptedScenario, 'roi'>, MemberVisibleSummary> = {
    claim: {
      id: 'member-result-claim',
      kind: 'claim_story',
      title: 'Claim update',
      summary: 'Your synthetic imaging claim is still in review and does not yet have a final outcome.',
      tone: 'info',
      badge: 'In Review',
      details: [
        { label: 'What happened', value: 'The provider submitted the claim after the service date.' },
        { label: 'Next step', value: 'Confirm that the provider supplied the required authorization record.' },
      ],
      source,
    },
    benefits: {
      id: 'member-result-benefits',
      kind: 'benefits',
      title: 'Coverage guidance',
      summary: 'The selected service is covered in network and requires prior authorization.',
      tone: 'success',
      badge: 'Covered',
      details: [
        { label: 'Prior authorization', value: 'Required' },
        {
          label: 'Cost',
          value: 'A final dollar total is unavailable until the allowed amount is known.',
        },
        { label: 'Next step', value: 'Ask the provider to confirm authorization before the service.' },
      ],
      source,
    },
    readiness: {
      id: 'member-result-readiness',
      kind: 'readiness',
      title: 'Rules-based claim readiness',
      summary: 'The synthetic claim is missing a required prior-authorization record.',
      tone: 'warning',
      badge: 'Needs attention',
      details: [
        {
          label: 'Why this was flagged',
          value: 'The service requires authorization, but the claim record does not show one.',
        },
        { label: 'Recommended action', value: 'Contact the provider before the claim completes review.' },
      ],
      source,
    },
    ambiguity: {
      id: 'member-result-ambiguity',
      kind: 'benefits',
      title: 'Which therapy service do you mean?',
      summary: 'I found more than one reviewed coverage rule and will not choose one silently.',
      tone: 'warning',
      badge: 'Clarification needed',
      details: [],
      choices: ['Physical therapy evaluation', 'Occupational therapy evaluation'],
      source,
    },
    escalation: {
      id: 'member-result-escalation',
      kind: 'escalation',
      title: 'Specialist review needed',
      summary: 'A claims specialist needs to review the record before a safe next step can be given.',
      tone: 'info',
      badge: 'Representative handoff',
      details: [
        { label: 'What happens next', value: 'Your conversation and the grounded findings continue with a representative.' },
      ],
      source,
    },
  }
  return summaries[scenario]
}

function scenarioFor(text: string): ScriptedScenario {
  const normalized = text.toLowerCase()
  if (normalized.includes('another adult') || normalized.includes('mother') || normalized.includes('father')) {
    return 'roi'
  }
  if (normalized.includes('therapy')) return 'ambiguity'
  if (normalized.includes('coverage') || normalized.includes('covered')) return 'benefits'
  if (normalized.includes('ready') || normalized.includes('authorization')) return 'readiness'
  if (normalized.includes('denial') || normalized.includes('denied')) return 'escalation'
  return 'claim'
}

export function scriptedMemberTurn(text: string, sequence: number): MemberConversationEvent[] {
  const scenario = scenarioFor(text)
  const userEvent: MemberConversationEvent = {
    id: `member-user-${sequence}`,
    type: 'message',
    message: {
      id: `member-user-${sequence}`,
      speaker: 'member',
      speakerLabel: 'You',
      text,
      timestamp: 'Now',
    },
  }
  const assistantCopy: Record<ScriptedScenario, string> = {
    claim: 'I found a synthetic claim record that matches this demonstration.',
    benefits: 'I found the reviewed synthetic coverage rule for this service.',
    readiness: 'I checked the synthetic claim against reviewed readiness rules.',
    roi: 'I can explain the authorization requirement without revealing member-specific information.',
    ambiguity: 'I need one detail before I can use the correct coverage rule.',
    escalation: 'The available record does not support a safe self-service next step.',
  }
  const result = projectMemberVisibleSummary(scenario, scenario !== 'roi')
  return [
    userEvent,
    assistantMessage(`member-assistant-${sequence}`, assistantCopy[scenario]),
    { id: `member-result-${sequence}`, type: 'result', result },
  ]
}
