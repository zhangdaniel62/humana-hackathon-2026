import type { StatusVariant } from '@/components/ui'

export type InteractionChannel = 'chat' | 'voice'
export type InteractionPhase = 'waiting' | 'active' | 'completed'
export type VoiceState = 'live' | 'held' | 'muted'
export type RoiStatus = 'verified' | 'not_required' | 'missing' | 'expired' | 'unknown'
export type InteractionSection = 'conversation' | 'findings' | 'details'
export type InteractionDisposition =
  | 'Resolved'
  | 'Follow-up required'
  | 'Transferred for specialist review'
  | 'Member disconnected'

export interface TranscriptMessage {
  id: string
  speaker: 'member' | 'assistant' | 'representative' | 'system'
  speakerLabel: string
  text: string
  timestamp: string
}

export interface RepresentativeFinding {
  id: string
  kind: 'claim_story' | 'benefits' | 'readiness' | 'roi' | 'notification'
  title: string
  summary: string
  tone: StatusVariant
  details: Array<{ label: string; value: string }>
  source: string
}

export interface ClaimDetails {
  memberId: string
  language: string
  planType: string
  claimId: string
  status: string
  provider: string
  service: string
  serviceDate: string
  submittedDate: string
  adjudicationDate: string | null
  cptCode: string
  billedAmount: string
  paidAmount: string
  timeline: Array<{ date: string; title: string; explanation: string }>
}

export interface RepresentativeInteraction {
  id: string
  memberLabel: string
  channel: InteractionChannel
  phase: InteractionPhase
  status: StatusVariant
  queuedAt: string
  waitingLabel: string
  pickedUpAt: string | null
  completedAt: string | null
  durationLabel: string | null
  topic: string
  memberNeed: string
  handoffReason: string
  recommendedNextStep: string
  groundedFinding: string
  roiStatus: RoiStatus
  claim: ClaimDetails | null
  transcript: TranscriptMessage[]
  findings: RepresentativeFinding[]
  intentHistory: RepresentativeFinding['kind'][]
  voiceState: VoiceState | null
  unreadCount: number
  tabOpen: boolean
  selectedSection: InteractionSection
  draft: string
  disposition: InteractionDisposition | null
  resolutionSummary: string | null
}

export interface RepresentativeDemoState {
  records: Record<string, RepresentativeInteraction>
  waitingIds: string[]
  activeIds: string[]
  completedIds: string[]
  openTabIds: string[]
  selectedInteractionId: string | null
}

const grounding = 'Synthetic claims fixture · exact record and reviewed rule fields'

function message(
  id: string,
  speaker: TranscriptMessage['speaker'],
  speakerLabel: string,
  text: string,
  timestamp: string,
): TranscriptMessage {
  return { id, speaker, speakerLabel, text, timestamp }
}

const baseClaim: ClaimDetails = {
  memberId: 'MBR00087',
  language: 'English',
  planType: 'PPO',
  claimId: 'CLM000377',
  status: 'In Review',
  provider: 'Riverside Orthopedics',
  service: 'Advanced diagnostic imaging',
  serviceDate: 'Jun 18, 2026',
  submittedDate: 'Jun 20, 2026',
  adjudicationDate: null,
  cptCode: '73221',
  billedAmount: '$1,240.00',
  paidAmount: '$0.00',
  timeline: [
    {
      date: 'Jun 18',
      title: 'Service received',
      explanation: 'Advanced diagnostic imaging was provided by Riverside Orthopedics.',
    },
    {
      date: 'Jun 20',
      title: 'Claim submitted',
      explanation: 'The provider submitted the claim for review.',
    },
    {
      date: 'Jul 17',
      title: 'In review',
      explanation: 'Required prior-authorization evidence is not attached to the synthetic record.',
    },
  ],
}

const readinessFinding: RepresentativeFinding = {
  id: 'finding-readiness',
  kind: 'readiness',
  title: 'Rules-based claim readiness',
  summary: 'A required prior authorization is not present on the In Review claim.',
  tone: 'danger',
  details: [
    { label: 'Risk band', value: 'High' },
    { label: 'Rule', value: 'MISSING_REQUIRED_PRIOR_AUTH' },
    { label: 'Evidence', value: 'prior_auth_required = true · prior_auth_obtained = false' },
    { label: 'Data completeness', value: '100% of required fields present' },
    { label: 'Recommended action', value: 'Confirm authorization with the provider before adjudication.' },
  ],
  source: grounding,
}

const claimFinding: RepresentativeFinding = {
  id: 'finding-claim',
  kind: 'claim_story',
  title: 'Claim Story',
  summary: 'The claim is still in review and does not yet have a final adjudication outcome.',
  tone: 'info',
  details: [
    { label: 'Claim', value: 'CLM000377' },
    { label: 'Current status', value: 'In Review' },
    { label: 'Confidence', value: '0.94' },
    { label: 'Escalation', value: 'Representative review requested' },
  ],
  source: 'Synthetic claims fixture · claim record CLM000377',
}

const benefitFinding: RepresentativeFinding = {
  id: 'finding-benefit',
  kind: 'benefits',
  title: 'Benefits guidance',
  summary: 'The service is covered in network, but the member’s phrase maps to two possible services.',
  tone: 'warning',
  details: [
    { label: 'Resolution', value: 'Clarification required' },
    { label: 'Choices', value: 'Physical therapy evaluation · Occupational therapy evaluation' },
    { label: 'Cost', value: 'A final dollar total is unavailable until an allowed amount is known.' },
  ],
  source: 'Synthetic coverage rules · RULE-PT-014 and RULE-OT-008',
}

const verifiedRoiFinding: RepresentativeFinding = {
  id: 'finding-roi-verified',
  kind: 'roi',
  title: 'Release of Information',
  summary: 'Disclosure is permitted for this caller and member pairing.',
  tone: 'success',
  details: [{ label: 'Status', value: 'Verified' }],
  source: 'Synthetic authorization fixture',
}

const blockedRoiFinding: RepresentativeFinding = {
  id: 'finding-roi-blocked',
  kind: 'roi',
  title: 'Authorization required',
  summary: 'Member-specific information must remain hidden until authorization is verified.',
  tone: 'danger',
  details: [{ label: 'Approved next step', value: 'Explain how the member can submit authorization.' }],
  source: 'Synthetic authorization decision',
}

const notificationFinding: RepresentativeFinding = {
  id: 'finding-notification',
  kind: 'notification',
  title: 'Notification preview',
  summary: 'Contact the provider to confirm required authorization before the claim completes review.',
  tone: 'info',
  details: [
    { label: 'Status', value: 'Preview · Not sent' },
    { label: 'Audience', value: 'Member' },
  ],
  source: 'Assembled from the synthetic readiness result',
}

const fixtures: RepresentativeInteraction[] = [
  {
    id: 'int-mia',
    memberLabel: 'Mia Rodriguez',
    channel: 'voice',
    phase: 'waiting',
    status: 'danger',
    queuedAt: '10:12 AM',
    waitingLabel: '18 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'In-review claim',
    memberNeed: 'Understand what is holding up an imaging claim.',
    handoffReason: 'Missing required prior-authorization evidence needs representative follow-up.',
    recommendedNextStep: 'Confirm the authorization record with the provider before adjudication.',
    groundedFinding: 'Required prior authorization is not present on an In Review claim.',
    roiStatus: 'verified',
    claim: baseClaim,
    transcript: [
      message('m1', 'member', 'Mia', 'Why is my imaging claim still being reviewed?', '10:08 AM'),
      message(
        'm2',
        'assistant',
        'Claim Assist',
        'I found the claim and a required authorization item that needs a representative to review.',
        '10:09 AM',
      ),
      message('m3', 'system', 'System', 'Escalated to the representative queue.', '10:12 AM'),
    ],
    findings: [readinessFinding, claimFinding, verifiedRoiFinding, notificationFinding],
    intentHistory: ['readiness', 'claim_story', 'roi', 'notification'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-jordan',
    memberLabel: 'Jordan Lee',
    channel: 'chat',
    phase: 'waiting',
    status: 'warning',
    queuedAt: '10:17 AM',
    waitingLabel: '13 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'Therapy coverage',
    memberNeed: 'Confirm coverage and cost for therapy.',
    handoffReason: 'The service phrase maps to more than one covered service.',
    recommendedNextStep: 'Ask whether the member means physical or occupational therapy.',
    groundedFinding: 'Two reviewed coverage rules match the member’s wording.',
    roiStatus: 'not_required',
    claim: { ...baseClaim, memberId: 'MBR00112', claimId: 'CLM000412', status: 'Pending' },
    transcript: [
      message('j1', 'member', 'Jordan', 'Is therapy covered under my plan?', '10:14 AM'),
      message(
        'j2',
        'assistant',
        'Claim Assist',
        'I can check, but I need to know whether you mean physical therapy or occupational therapy.',
        '10:15 AM',
      ),
      message('j3', 'system', 'System', 'Member requested a representative.', '10:17 AM'),
    ],
    findings: [benefitFinding, verifiedRoiFinding],
    intentHistory: ['benefits', 'roi'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-priya',
    memberLabel: 'Priya Shah',
    channel: 'voice',
    phase: 'waiting',
    status: 'info',
    queuedAt: '10:20 AM',
    waitingLabel: '10 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'Denied claim',
    memberNeed: 'Understand a denial with incomplete supporting evidence.',
    handoffReason: 'The claim story cannot safely determine the required appeal step.',
    recommendedNextStep: 'Review the missing documentation with a claims specialist.',
    groundedFinding: 'The denial record is incomplete and requires specialist review.',
    roiStatus: 'verified',
    claim: { ...baseClaim, memberId: 'MBR00134', claimId: 'CLM000438', status: 'Denied' },
    transcript: [
      message('p1', 'member', 'Priya', 'What do I need to do about this denial?', '10:18 AM'),
      message(
        'p2',
        'assistant',
        'Claim Assist',
        'The record does not include enough reviewed evidence for me to give a safe appeal step.',
        '10:19 AM',
      ),
    ],
    findings: [claimFinding, verifiedRoiFinding],
    intentHistory: ['claim_story', 'roi'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-auth',
    memberLabel: 'Caller awaiting authorization',
    channel: 'chat',
    phase: 'waiting',
    status: 'danger',
    queuedAt: '10:23 AM',
    waitingLabel: '7 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'Authorization help',
    memberNeed: 'Learn how to obtain permission to discuss another adult member’s claim.',
    handoffReason: 'Release of Information authorization is missing.',
    recommendedNextStep: 'Explain the approved authorization submission process without disclosing claim facts.',
    groundedFinding: 'Disclosure is blocked until authorization is verified.',
    roiStatus: 'missing',
    claim: null,
    transcript: [
      message('a1', 'member', 'Caller', 'I am calling about another adult family member.', '10:21 AM'),
      message(
        'a2',
        'assistant',
        'Claim Assist',
        'I cannot share member-specific information without authorization, but I can explain the next step.',
        '10:22 AM',
      ),
    ],
    findings: [blockedRoiFinding],
    intentHistory: ['roi'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-ava',
    memberLabel: 'Ava Thompson',
    channel: 'chat',
    phase: 'waiting',
    status: 'warning',
    queuedAt: '10:25 AM',
    waitingLabel: '5 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'Claim next step',
    memberNeed: 'Confirm the next step for a denied outpatient claim.',
    handoffReason: 'The denial code is not in the reviewed guidance table.',
    recommendedNextStep: 'Route the record to a claims specialist rather than guessing.',
    groundedFinding: 'The denial outcome is known, but the code is unsupported.',
    roiStatus: 'verified',
    claim: { ...baseClaim, memberId: 'MBR00155', claimId: 'CLM000455', status: 'Denied' },
    transcript: [
      message('v1', 'member', 'Ava', 'What should I do next?', '10:24 AM'),
      message('v2', 'assistant', 'Claim Assist', 'A claims specialist needs to review this denial code.', '10:25 AM'),
    ],
    findings: [claimFinding, verifiedRoiFinding],
    intentHistory: ['claim_story', 'roi'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-ethan',
    memberLabel: 'Ethan Brooks',
    channel: 'voice',
    phase: 'waiting',
    status: 'info',
    queuedAt: '10:27 AM',
    waitingLabel: '3 min',
    pickedUpAt: null,
    completedAt: null,
    durationLabel: null,
    topic: 'Provider guidance',
    memberNeed: 'Find an in-network provider for a covered service.',
    handoffReason: 'The member requested help choosing between available providers.',
    recommendedNextStep: 'Review the grounded provider choices without inventing distance.',
    groundedFinding: 'Two in-network providers are accepting new patients.',
    roiStatus: 'not_required',
    claim: { ...baseClaim, memberId: 'MBR00173', claimId: 'CLM000478', status: 'Pending' },
    transcript: [
      message('e1', 'member', 'Ethan', 'Can you help me choose an in-network provider?', '10:26 AM'),
      message('e2', 'assistant', 'Claim Assist', 'I found two grounded choices and can connect you for help.', '10:27 AM'),
    ],
    findings: [benefitFinding],
    intentHistory: ['benefits'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: null,
    resolutionSummary: null,
  },
  {
    id: 'int-olivia',
    memberLabel: 'Olivia Chen',
    channel: 'chat',
    phase: 'completed',
    status: 'success',
    queuedAt: '9:42 AM',
    waitingLabel: '6 min',
    pickedUpAt: '9:48 AM',
    completedAt: '10:02 AM',
    durationLabel: '14 min',
    topic: 'Coverage clarification',
    memberNeed: 'Confirm whether an outpatient service required prior authorization.',
    handoffReason: 'The member asked for representative confirmation.',
    recommendedNextStep: 'Confirm the reviewed coverage rule and provide the next step.',
    groundedFinding: 'The covered service requires prior authorization.',
    roiStatus: 'not_required',
    claim: { ...baseClaim, memberId: 'MBR00064', claimId: 'CLM000351', status: 'Pending' },
    transcript: [
      message('o1', 'member', 'Olivia', 'Do I need approval before this outpatient service?', '9:44 AM'),
      message('o2', 'assistant', 'Claim Assist', 'The reviewed rule says prior authorization is required.', '9:45 AM'),
      message('o3', 'representative', 'Representative', 'I confirmed the requirement and sent the provider instructions.', '10:00 AM'),
    ],
    findings: [benefitFinding],
    intentHistory: ['benefits'],
    voiceState: null,
    unreadCount: 0,
    tabOpen: false,
    selectedSection: 'conversation',
    draft: '',
    disposition: 'Resolved',
    resolutionSummary: 'Confirmed prior-authorization requirements and provided the approved next step.',
  },
]

export function createRepresentativeDemoState(): RepresentativeDemoState {
  const records = Object.fromEntries(
    fixtures.map((fixture) => [fixture.id, structuredClone(fixture)]),
  ) as Record<string, RepresentativeInteraction>
  return {
    records,
    waitingIds: fixtures.filter((item) => item.phase === 'waiting').map((item) => item.id),
    activeIds: [],
    completedIds: fixtures.filter((item) => item.phase === 'completed').map((item) => item.id),
    openTabIds: [],
    selectedInteractionId: null,
  }
}

export function canDisclose(interaction: RepresentativeInteraction): boolean {
  return interaction.roiStatus === 'verified' || interaction.roiStatus === 'not_required'
}

export function statusLabel(interaction: RepresentativeInteraction): string {
  if (interaction.phase === 'completed') return interaction.disposition ?? 'Completed'
  if (interaction.channel === 'voice' && interaction.voiceState) {
    return interaction.voiceState[0].toUpperCase() + interaction.voiceState.slice(1)
  }
  if (interaction.roiStatus === 'missing' || interaction.roiStatus === 'expired') {
    return 'Authorization required'
  }
  return interaction.channel === 'chat' ? 'Chat handoff' : 'Voice handoff'
}

export function roiLabel(status: RoiStatus): string {
  return {
    verified: 'Verified',
    not_required: 'Not required',
    missing: 'Missing',
    expired: 'Expired',
    unknown: 'Unknown',
  }[status]
}

export const dispositions: InteractionDisposition[] = [
  'Resolved',
  'Follow-up required',
  'Transferred for specialist review',
  'Member disconnected',
]
