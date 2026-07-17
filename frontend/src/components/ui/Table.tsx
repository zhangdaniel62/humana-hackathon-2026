import {
  Cell as AriaCell,
  Column as AriaColumn,
  Row as AriaRow,
  Table as AriaTable,
  TableBody as AriaTableBody,
  TableHeader as AriaTableHeader,
  type CellProps,
  type ColumnProps,
  type RowProps,
  type TableBodyProps,
  type TableHeaderProps,
  type TableProps,
} from 'react-aria-components'
import { cn } from '@/lib/cn'

export function Table({ className, ...props }: Omit<TableProps, 'className'> & { className?: string }) {
  return (
    <AriaTable
      {...props}
      className={cn('w-full border-separate border-spacing-0 text-regular', className)}
    />
  )
}

export function TableHeader<T extends object>({
  className,
  ...props
}: Omit<TableHeaderProps<T>, 'className'> & { className?: string }) {
  return <AriaTableHeader {...props} className={cn(className)} />
}

export function Column({
  className,
  ...props
}: Omit<ColumnProps, 'className'> & { className?: string }) {
  return (
    <AriaColumn
      {...props}
      className={cn(
        'border-b border-border-primary px-3 py-2 text-left text-small font-medium text-text-tertiary',
        className,
      )}
    />
  )
}

export function TableBody<T extends object>({
  className,
  ...props
}: Omit<TableBodyProps<T>, 'className'> & { className?: string }) {
  return <AriaTableBody {...props} className={cn(className)} />
}

export function Row<T extends object>({
  className,
  ...props
}: Omit<RowProps<T>, 'className'> & { className?: string }) {
  return (
    <AriaRow
      {...props}
      className={cn('transition-colors data-hovered:bg-bg-secondary', className)}
    />
  )
}

export function Cell({ className, ...props }: Omit<CellProps, 'className'> & { className?: string }) {
  return (
    <AriaCell
      {...props}
      className={cn('h-10 border-b border-border-secondary px-3 py-2 text-text-secondary', className)}
    />
  )
}
