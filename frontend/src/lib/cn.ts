type ClassValue = string | false | null | undefined

/** Joins truthy class strings. No conflict merging — keep call sites conflict-free. */
export function cn(...classes: ClassValue[]): string {
  return classes.filter(Boolean).join(' ')
}
