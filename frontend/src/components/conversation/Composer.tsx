import { TextArea, TextField } from 'react-aria-components'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui'
import { clampMemberDraft } from '@/lib/memberDemo'

export function Composer({
  value,
  onChange,
  onSend,
  placeholder = 'Write a message…',
  ariaLabel = 'Message',
  isDisabled = false,
}: {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  placeholder?: string
  ariaLabel?: string
  isDisabled?: boolean
}) {
  const updateValue = (nextValue: string) => onChange(clampMemberDraft(nextValue))

  const send = () => {
    if (value.trim()) onSend()
  }

  return (
    <TextField
      aria-label={ariaLabel}
      value={value}
      onChange={updateValue}
      isDisabled={isDisabled}
      className="rounded-md border border-border-primary bg-bg-primary p-2"
    >
      <TextArea
        rows={2}
        maxLength={4000}
        placeholder={placeholder}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            send()
          }
        }}
        className="max-h-36 min-h-12 w-full resize-none bg-transparent px-1 py-1 text-regular text-text-primary placeholder:text-text-tertiary"
      />
      <div className="mt-1 flex items-center justify-between gap-3">
        <span className="text-micro text-text-quaternary">Enter to send · Shift+Enter for a new line</span>
        <Button variant="primary" size="sm" isDisabled={isDisabled || !value.trim()} onPress={send}>
          <Send size={14} strokeWidth={1.5} aria-hidden="true" />
          Send
        </Button>
      </div>
    </TextField>
  )
}
