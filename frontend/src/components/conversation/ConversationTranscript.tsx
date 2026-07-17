import type { TranscriptMessage } from '@/lib/representativeDemo'
import { cn } from '@/lib/cn'

export function ConversationTranscript({
  messages,
  className,
}: {
  messages: TranscriptMessage[]
  className?: string
}) {
  return (
    <section aria-label="Conversation transcript" className={cn('flex flex-col', className)}>
      {messages.map((item) =>
        item.speaker === 'system' ? (
          <div
            key={item.id}
            className="border-y border-border-tertiary py-2 text-center text-micro text-text-quaternary"
          >
            {item.text}
          </div>
        ) : (
          <article key={item.id} className="grid grid-cols-[112px_minmax(0,1fr)] gap-4 py-3">
            <div>
              <p className="text-small font-medium text-text-primary">{item.speakerLabel}</p>
              <time className="text-micro text-text-quaternary">{item.timestamp}</time>
            </div>
            <p
              className={cn(
                'text-regular leading-6 text-text-secondary',
                item.speaker === 'representative' && 'text-text-primary',
              )}
            >
              {item.text}
            </p>
          </article>
        ),
      )}
    </section>
  )
}
