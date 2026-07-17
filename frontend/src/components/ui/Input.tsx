import {
  FieldError,
  Input as AriaInput,
  Label,
  Text,
  TextField,
  type TextFieldProps,
  type ValidationResult,
} from 'react-aria-components'
import { cn } from '@/lib/cn'

export interface InputProps extends Omit<TextFieldProps, 'className'> {
  label?: string
  description?: string
  errorMessage?: string | ((validation: ValidationResult) => string)
  placeholder?: string
  size?: 'default' | 'sm'
  className?: string
}

export function Input({
  label,
  description,
  errorMessage,
  placeholder,
  size = 'default',
  className,
  ...props
}: InputProps) {
  return (
    <TextField {...props} className={cn('flex flex-col gap-1', className)}>
      {label && <Label className="text-small font-medium text-text-secondary">{label}</Label>}
      <AriaInput
        placeholder={placeholder}
        className={cn(
          'w-full rounded-md border border-border-primary bg-bg-secondary px-2.5 text-regular text-text-primary transition-colors placeholder:text-text-tertiary',
          'data-focused:border-accent',
          'data-disabled:bg-bg-primary data-disabled:text-text-tertiary',
          'data-invalid:border-danger',
          size === 'sm' ? 'h-7' : 'h-8',
        )}
      />
      {description && (
        <Text slot="description" className="text-mini text-text-tertiary">
          {description}
        </Text>
      )}
      <FieldError className="text-mini text-danger">{errorMessage}</FieldError>
    </TextField>
  )
}
