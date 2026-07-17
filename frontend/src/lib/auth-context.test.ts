import { describe, expect, it } from 'vitest'
import { canAccessPath, landingPathFor, type User } from './auth-context'

const users = {
  manager: {
    id: 1,
    username: 'manager',
    name: 'manager',
    role: 'manager',
    capabilities: ['manager_dashboard'],
  },
  customer: {
    id: 2,
    username: 'customer',
    name: 'customer',
    role: 'customer',
    capabilities: ['chat', 'voice'],
  },
  rep: {
    id: 3,
    username: 'rep',
    name: 'rep',
    role: 'rep',
    capabilities: ['rep_queue', 'chat', 'voice'],
  },
} satisfies Record<string, User>

describe('role-aware routing', () => {
  it('lands each backend role on its own surface', () => {
    expect(landingPathFor(users.manager)).toBe('/')
    expect(landingPathFor(users.customer)).toBe('/member')
    expect(landingPathFor(users.rep)).toBe('/queue')
  })

  it('keeps the manager on dashboard routes only', () => {
    expect(canAccessPath(users.manager, '/')).toBe(true)
    expect(canAccessPath(users.manager, '/metrics/average-handle-time')).toBe(true)
    expect(canAccessPath(users.manager, '/queue')).toBe(false)
    expect(canAccessPath(users.manager, '/member')).toBe(false)
  })

  it('keeps customers and representatives off manager routes', () => {
    expect(canAccessPath(users.customer, '/member')).toBe(true)
    expect(canAccessPath(users.customer, '/')).toBe(false)
    expect(canAccessPath(users.rep, '/queue')).toBe(true)
    expect(canAccessPath(users.rep, '/workspace')).toBe(true)
    expect(canAccessPath(users.rep, '/')).toBe(false)
  })

  it('rejects external-looking redirect paths', () => {
    expect(canAccessPath(users.manager, '//evil.example')).toBe(false)
  })
})
