import { apiFetch } from './api'

export interface SessionSummaryPayload {
  session_id: string
  status: 'ready' | 'incomplete'
  roi: Record<string, unknown> | null
  claim: Record<string, unknown> | null
  benefits: Record<string, unknown> | null
  readiness: Record<string, unknown> | null
  notification_preview: Record<string, unknown> | null
  missing_findings: string[]
}

export interface ProjectedSummaryDetail {
  label: string
  value: string
}

export interface ProjectedSummarySection {
  key: 'roi' | 'claim' | 'benefits' | 'readiness' | 'notification'
  title: string
  status: string | null
  summary: string | null
  details: ProjectedSummaryDetail[]
}

export interface ProjectedSessionSummary {
  sessionId: string
  status: 'ready' | 'incomplete'
  missingFindings: string[]
  sections: ProjectedSummarySection[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null
}

function firstString(record: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
    : []
}

function displayBoolean(value: unknown, trueLabel: string, falseLabel: string): string | null {
  if (value === true) return trueLabel
  if (value === false) return falseLabel
  return null
}

function addDetail(
  details: ProjectedSummaryDetail[],
  label: string,
  value: string | number | null | undefined,
): void {
  if (typeof value === 'string' && value.trim()) details.push({ label, value: value.trim() })
  if (typeof value === 'number' && Number.isFinite(value)) details.push({ label, value: String(value) })
}

function projectRoi(value: Record<string, unknown>): ProjectedSummarySection {
  const details: ProjectedSummaryDetail[] = []
  addDetail(details, 'Reason', firstString(value, ['reason']))
  return {
    key: 'roi',
    title: 'Authorization',
    status: firstString(value, ['status']),
    summary: firstString(value, ['message']),
    details,
  }
}

function projectClaim(value: Record<string, unknown>): ProjectedSummarySection {
  const story = recordOrNull(value.story) ?? value
  const denial = recordOrNull(story.denial)
  const details: ProjectedSummaryDetail[] = []
  addDetail(details, 'Provider', firstString(story, ['provider_name']))
  addDetail(details, 'Service', firstString(story, ['service_description', 'service_code']))
  addDetail(details, 'Denial reason', denial ? firstString(denial, ['reason']) : null)
  for (const action of stringList(denial?.required_actions)) addDetail(details, 'Required action', action)
  return {
    key: 'claim',
    title: 'Claim',
    status: firstString(story, ['current_status']) ?? firstString(value, ['status']),
    summary: firstString(story, ['summary']) ?? firstString(value, ['message']),
    details,
  }
}

function projectBenefits(value: Record<string, unknown>): ProjectedSummarySection {
  const details: ProjectedSummaryDetail[] = []
  addDetail(details, 'Coverage', displayBoolean(value.covered, 'Covered', 'Not covered'))
  addDetail(
    details,
    'Prior authorization',
    displayBoolean(value.prior_auth_required, 'Required', 'Not required'),
  )
  const cost = recordOrNull(value.cost)
  addDetail(details, 'Cost', cost ? firstString(cost, ['estimate_text', 'dollar_total_reason']) : null)
  addDetail(details, 'Next step', firstString(value, ['next_step']))
  return {
    key: 'benefits',
    title: 'Coverage',
    status: firstString(value, ['status', 'resolution']),
    summary: firstString(value, ['answer_text', 'message']),
    details,
  }
}

function projectReadiness(value: Record<string, unknown>): ProjectedSummarySection {
  const assessment = recordOrNull(value.assessment) ?? value
  const details: ProjectedSummaryDetail[] = []
  for (const action of stringList(assessment.recommended_actions)) {
    addDetail(details, 'Recommended action', action)
  }
  const factors = Array.isArray(assessment.factors) ? assessment.factors : []
  for (const factorValue of factors) {
    const factor = recordOrNull(factorValue)
    if (!factor) continue
    const title = firstString(factor, ['title'])
    const action = firstString(factor, ['recommended_action'])
    if (title) addDetail(details, 'Finding', title)
    if (action) addDetail(details, 'Recommended action', action)
  }
  return {
    key: 'readiness',
    title: 'Claim readiness',
    status: firstString(assessment, ['risk_band']) ?? firstString(value, ['status']),
    summary: firstString(assessment, ['summary']) ?? firstString(value, ['message']),
    details,
  }
}

function projectNotification(value: Record<string, unknown>): ProjectedSummarySection {
  const details: ProjectedSummaryDetail[] = []
  addDetail(details, 'Delivery status', firstString(value, ['delivery_status']))
  for (const action of stringList(value.recommended_actions)) addDetail(details, 'Recommended action', action)
  return {
    key: 'notification',
    title: firstString(value, ['subject']) ?? 'Notification preview',
    status: firstString(value, ['status']),
    summary: firstString(value, ['message']),
    details,
  }
}

/** Keep the incomplete state valid and project only explicitly returned backend fields. */
export function projectSessionSummary(value: unknown): ProjectedSessionSummary | null {
  if (!isRecord(value) || typeof value.session_id !== 'string') return null
  if (value.status !== 'ready' && value.status !== 'incomplete') return null

  const sections: ProjectedSummarySection[] = []
  const roi = recordOrNull(value.roi)
  const claim = recordOrNull(value.claim)
  const benefits = recordOrNull(value.benefits)
  const readiness = recordOrNull(value.readiness)
  const notification = recordOrNull(value.notification_preview)
  if (roi) sections.push(projectRoi(roi))
  if (claim) sections.push(projectClaim(claim))
  if (benefits) sections.push(projectBenefits(benefits))
  if (readiness) sections.push(projectReadiness(readiness))
  if (notification) sections.push(projectNotification(notification))

  return {
    sessionId: value.session_id,
    status: value.status,
    missingFindings: stringList(value.missing_findings),
    sections,
  }
}

export function summaryApiPath(summaryUrl: string): string | null {
  if (!summaryUrl.startsWith('/')) return null
  return summaryUrl
}

export async function fetchConversationSummary(summaryUrl: string): Promise<ProjectedSessionSummary> {
  const path = summaryApiPath(summaryUrl)
  if (!path) throw new Error('The server returned an invalid session summary URL.')
  const raw = await apiFetch<SessionSummaryPayload>(path)
  const projected = projectSessionSummary(raw)
  if (!projected) throw new Error('The server returned an invalid session summary.')
  return projected
}
