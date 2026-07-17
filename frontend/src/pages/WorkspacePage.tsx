import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog,
  DialogTrigger,
  Heading,
  Modal,
  ModalOverlay,
  Radio,
  RadioGroup,
} from 'react-aria-components'
import { MessageSquare, Mic, MicOff, Pause, Play } from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import { useSessions } from '@/app/sessions-context'
import { PageHeader } from '@/components/PageHeader'
import { Composer } from '@/components/conversation/Composer'
import { ConversationTranscript } from '@/components/conversation/ConversationTranscript'
import { ResultPanel } from '@/components/conversation/ResultPanel'
import {
  Badge,
  Button,
  Panel,
  Tab,
  TabList,
  TabPanel,
  Tabs,
} from '@/components/ui'
import {
  canDisclose,
  dispositions,
  roiLabel,
  statusLabel,
  type InteractionDisposition,
  type RepresentativeFinding,
  type RepresentativeInteraction,
} from '@/lib/representativeDemo'

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 py-1.5">
      <dt className="text-small text-text-tertiary">{label}</dt>
      <dd className="text-small text-text-secondary">{value}</dd>
    </div>
  )
}

function HandoffBrief({ interaction }: { interaction: RepresentativeInteraction }) {
  return (
    <Panel dense className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-small font-medium text-text-primary">Handoff brief</h2>
        <Badge variant={interaction.status}>{statusLabel(interaction)}</Badge>
      </div>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 xl:grid-cols-2">
        <div>
          <dt className="text-mini text-text-tertiary">Member asked</dt>
          <dd className="mt-0.5 text-small text-text-secondary">{interaction.memberNeed}</dd>
        </div>
        <div>
          <dt className="text-mini text-text-tertiary">Claim Assist handed off because</dt>
          <dd className="mt-0.5 text-small text-text-secondary">{interaction.handoffReason}</dd>
        </div>
        <div>
          <dt className="text-mini text-text-tertiary">Recommended next step</dt>
          <dd className="mt-0.5 text-small text-text-secondary">
            {interaction.recommendedNextStep}
          </dd>
        </div>
        <div>
          <dt className="text-mini text-text-tertiary">Grounding</dt>
          <dd className="mt-0.5 text-small text-text-secondary">{interaction.groundedFinding}</dd>
        </div>
      </dl>
    </Panel>
  )
}

function FindingPanel({ finding }: { finding: RepresentativeFinding }) {
  return (
    <ResultPanel
      title={finding.title}
      summary={finding.summary}
      tone={finding.tone}
      badge={
        finding.kind === 'notification'
          ? 'Preview · Not sent'
          : finding.kind === 'readiness'
            ? 'Rules-based'
            : undefined
      }
      source={finding.source}
    >
      {finding.details.length > 0 && (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 xl:grid-cols-2">
          {finding.details.map((detail) => (
            <div key={detail.label}>
              <dt className="text-mini text-text-tertiary">{detail.label}</dt>
              <dd className="mt-0.5 text-small text-text-secondary">{detail.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </ResultPanel>
  )
}

function CompletionDialog({ interaction }: { interaction: RepresentativeInteraction }) {
  const { completeInteraction } = useSessions()
  const [disposition, setDisposition] = useState<InteractionDisposition | null>(null)

  return (
    <DialogTrigger>
      <Button variant="secondary">End interaction</Button>
      <ModalOverlay
        isDismissable
        className="fixed inset-0 z-50 flex items-center justify-center bg-text-primary/15 p-4"
      >
        <Modal className="w-full max-w-md rounded-md border border-border-primary bg-bg-primary shadow-float data-entering:animate-pop-in data-exiting:animate-pop-out">
          <Dialog className="p-4 outline-none">
            {({ close }) => (
              <>
                <Heading slot="title" className="text-large font-medium text-text-primary">
                  End interaction
                </Heading>
                <p className="mt-1 text-small text-text-secondary">
                  Record the outcome before moving {interaction.memberLabel} to Completed.
                </p>
                <RadioGroup
                  aria-label="Interaction disposition"
                  value={disposition}
                  onChange={(value) => setDisposition(value as InteractionDisposition)}
                  className="mt-4 flex flex-col gap-1"
                >
                  {dispositions.map((option) => (
                    <Radio
                      key={option}
                      value={option}
                      className="group flex cursor-default items-center gap-2 rounded-md px-2 py-2 text-small text-text-secondary data-hovered:bg-bg-secondary data-selected:text-text-primary"
                    >
                      <span className="flex size-4 items-center justify-center rounded-full border border-border-primary group-data-selected:border-accent">
                        <span className="size-2 rounded-full bg-accent opacity-0 group-data-selected:opacity-100" />
                      </span>
                      {option}
                    </Radio>
                  ))}
                </RadioGroup>
                <div className="mt-4 flex justify-end gap-2">
                  <Button variant="ghost" onPress={close}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    isDisabled={!disposition}
                    onPress={() => {
                      if (disposition) completeInteraction(interaction.id, disposition)
                      close()
                    }}
                  >
                    Complete interaction
                  </Button>
                </div>
              </>
            )}
          </Dialog>
        </Modal>
      </ModalOverlay>
    </DialogTrigger>
  )
}

function ConversationTab({ interaction }: { interaction: RepresentativeInteraction }) {
  const { setDraft, sendRepresentativeMessage, resumeVoice, toggleMute } = useSessions()

  return (
    <div className="flex flex-col gap-4">
      <HandoffBrief interaction={interaction} />
      <div>
        <h2 className="mb-1 text-small font-medium text-text-primary">Conversation</h2>
        <ConversationTranscript messages={interaction.transcript} />
      </div>
      {interaction.channel === 'chat' ? (
        <Composer
          value={interaction.draft}
          onChange={(value) => setDraft(interaction.id, value)}
          onSend={() => sendRepresentativeMessage(interaction.id)}
          ariaLabel={`Message ${interaction.memberLabel}`}
        />
      ) : (
        <Panel dense className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {interaction.voiceState === 'held' ? (
              <Pause size={16} strokeWidth={1.5} aria-hidden="true" className="text-warning" />
            ) : interaction.voiceState === 'muted' ? (
              <MicOff size={16} strokeWidth={1.5} aria-hidden="true" className="text-text-tertiary" />
            ) : (
              <Mic size={16} strokeWidth={1.5} aria-hidden="true" className="text-success" />
            )}
            <div>
              <p className="text-small font-medium text-text-primary">
                Voice · {statusLabel(interaction)}
              </p>
              <p className="text-micro text-text-quaternary">
                Synthetic interaction state · no microphone or audio connection
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {interaction.voiceState === 'held' ? (
              <Button variant="primary" onPress={() => resumeVoice(interaction.id)}>
                <Play size={14} strokeWidth={1.5} aria-hidden="true" />
                Resume
              </Button>
            ) : (
              <Button variant="secondary" onPress={() => toggleMute(interaction.id)}>
                {interaction.voiceState === 'muted' ? 'Unmute' : 'Mute'}
              </Button>
            )}
          </div>
        </Panel>
      )}
    </div>
  )
}

function FindingsTab({ interaction }: { interaction: RepresentativeInteraction }) {
  const visibleFindings = canDisclose(interaction)
    ? interaction.intentHistory
        .map((kind) => interaction.findings.find((finding) => finding.kind === kind))
        .filter((finding): finding is RepresentativeFinding => Boolean(finding))
    : interaction.findings.filter((finding) => finding.kind === 'roi')

  return (
    <div className="flex flex-col gap-3">
      {visibleFindings.map((finding) => (
        <FindingPanel key={finding.id} finding={finding} />
      ))}
    </div>
  )
}

function MemberClaimTab({ interaction }: { interaction: RepresentativeInteraction }) {
  if (!canDisclose(interaction)) {
    return (
      <ResultPanel
        title="Authorization required"
        summary="Member and claim details remain hidden until Release of Information authorization is verified. Explain the approved authorization submission process without disclosing record facts."
        tone="danger"
        badge="Restricted"
      />
    )
  }

  if (!interaction.claim) {
    return (
      <Panel>
        <p className="text-regular text-text-tertiary">No claim is linked to this interaction.</p>
      </Panel>
    )
  }

  const claim = interaction.claim
  return (
    <div className="flex flex-col gap-4">
      <Panel dense>
        <h2 className="text-small font-medium text-text-primary">Member and claim</h2>
        <dl className="mt-2 grid grid-cols-1 gap-x-8 md:grid-cols-2">
          <DetailRow label="Member" value={claim.memberId} />
          <DetailRow label="Language" value={claim.language} />
          <DetailRow label="Plan" value={claim.planType} />
          <DetailRow label="Claim" value={claim.claimId} />
          <DetailRow label="Status" value={claim.status} />
          <DetailRow label="Provider" value={claim.provider} />
          <DetailRow label="Service" value={`${claim.cptCode} · ${claim.service}`} />
          <DetailRow label="Service date" value={claim.serviceDate} />
          <DetailRow label="Submitted" value={claim.submittedDate} />
          <DetailRow label="Adjudicated" value={claim.adjudicationDate ?? '— · Not adjudicated'} />
          <DetailRow label="Billed" value={claim.billedAmount} />
          <DetailRow label="Paid" value={claim.paidAmount} />
        </dl>
      </Panel>
      <Panel dense>
        <h2 className="text-small font-medium text-text-primary">Claim timeline</h2>
        <ol className="mt-2 flex flex-col">
          {claim.timeline.map((event) => (
            <li key={`${event.date}-${event.title}`} className="grid grid-cols-[72px_minmax(0,1fr)] gap-4 border-t border-border-tertiary py-3 first:border-0">
              <time className="text-small text-text-tertiary">{event.date}</time>
              <div>
                <p className="text-small font-medium text-text-primary">{event.title}</p>
                <p className="mt-0.5 text-small text-text-secondary">{event.explanation}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="border-t border-border-tertiary pt-2 text-micro text-text-quaternary">
          Grounded in the synthetic claim record and displayed fields only.
        </p>
      </Panel>
    </div>
  )
}

function PropertiesRail({ interaction }: { interaction: RepresentativeInteraction }) {
  const { user } = useAuth()
  const disclosed = canDisclose(interaction)
  return (
    <aside className="w-72 shrink-0 border-l border-border-secondary bg-bg-secondary p-4">
      <div className="flex flex-col gap-6">
        <section>
          <h2 className="text-small font-medium text-text-primary">Interaction</h2>
          <dl className="mt-2">
            <DetailRow label="Channel" value={interaction.channel === 'voice' ? 'Voice' : 'Chat'} />
            <DetailRow label="State" value={statusLabel(interaction)} />
            <DetailRow label="Representative" value={user?.name ?? 'Representative'} />
            <DetailRow label="Queued" value={interaction.queuedAt} />
            <DetailRow label="Picked up" value={interaction.pickedUpAt ?? '—'} />
          </dl>
        </section>
        <section>
          <h2 className="text-small font-medium text-text-primary">Authorization</h2>
          <div className="mt-2">
            <Badge
              variant={
                disclosed
                  ? 'success'
                  : interaction.roiStatus === 'unknown'
                    ? 'warning'
                    : 'danger'
              }
            >
              {roiLabel(interaction.roiStatus)}
            </Badge>
          </div>
        </section>
        <section>
          <h2 className="text-small font-medium text-text-primary">Reference</h2>
          <p className="mt-2 text-small text-text-secondary">
            {disclosed && interaction.claim ? interaction.claim.claimId : 'Hidden until authorized'}
          </p>
        </section>
        <CompletionDialog interaction={interaction} />
      </div>
    </aside>
  )
}

export function WorkspacePage() {
  const navigate = useNavigate()
  const { activeInteractions, selectedInteraction, setSection } = useSessions()

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Active Interactions"
        description="Concurrent member handoffs with preserved conversation, grounded AI findings, and modality-specific representative controls."
        actions={<Badge variant="neutral">Synthetic demo data</Badge>}
      />
      {!selectedInteraction ? (
        <div className="flex flex-1 items-center justify-center p-6 text-center">
          <div className="max-w-sm">
            <h2 className="text-large font-medium text-text-primary">
              {activeInteractions.length > 0 ? 'No interaction tab is open' : 'No active interactions'}
            </h2>
            <p className="mt-1 text-regular text-text-tertiary">
              {activeInteractions.length > 0
                ? 'Use the plus control above to reopen a hidden active interaction.'
                : 'Pick up the oldest handoff from the Interaction Queue to begin.'}
            </p>
            {activeInteractions.length === 0 && (
              <Button className="mt-4" variant="primary" onPress={() => navigate('/queue')}>
                Open Interaction Queue
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 p-6">
            <div className="mb-4 flex items-center gap-2">
              {selectedInteraction.channel === 'voice' ? (
                <Mic size={16} strokeWidth={1.5} aria-hidden="true" className="text-text-tertiary" />
              ) : (
                <MessageSquare
                  size={16}
                  strokeWidth={1.5}
                  aria-hidden="true"
                  className="text-text-tertiary"
                />
              )}
              <h2 className="text-large font-medium text-text-primary">
                {selectedInteraction.memberLabel}
              </h2>
            </div>
            <Tabs
              selectedKey={selectedInteraction.selectedSection}
              onSelectionChange={(key) =>
                setSection(
                  selectedInteraction.id,
                  key === 'findings' ? 'findings' : key === 'details' ? 'details' : 'conversation',
                )
              }
            >
              <TabList aria-label="Interaction sections">
                <Tab id="conversation">Conversation</Tab>
                <Tab id="findings">AI Findings</Tab>
                <Tab id="details">Member &amp; Claim</Tab>
              </TabList>
              <TabPanel id="conversation">
                <ConversationTab interaction={selectedInteraction} />
              </TabPanel>
              <TabPanel id="findings">
                <FindingsTab interaction={selectedInteraction} />
              </TabPanel>
              <TabPanel id="details">
                <MemberClaimTab interaction={selectedInteraction} />
              </TabPanel>
            </Tabs>
          </main>
          <PropertiesRail interaction={selectedInteraction} />
        </div>
      )}
    </div>
  )
}
