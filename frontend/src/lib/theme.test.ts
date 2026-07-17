import { describe, expect, it } from 'vitest'
import { isThemePreference, resolveTheme } from './theme'

describe('theme preferences', () => {
  it('accepts only supported persisted values', () => {
    expect(isThemePreference('light')).toBe(true)
    expect(isThemePreference('dark')).toBe(true)
    expect(isThemePreference('system')).toBe(true)
    expect(isThemePreference('contrast')).toBe(false)
    expect(isThemePreference(null)).toBe(false)
  })

  it('resolves an explicit preference or follows the system', () => {
    expect(resolveTheme('light', 'dark')).toBe('light')
    expect(resolveTheme('dark', 'light')).toBe('dark')
    expect(resolveTheme('system', 'dark')).toBe('dark')
    expect(resolveTheme('system', 'light')).toBe('light')
  })
})
