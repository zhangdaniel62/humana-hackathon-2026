import {
  createRepresentativeDemoState,
  type RepresentativeDemoState,
} from './representativeDemo'

export type RepresentativeDemoScenario = 'default' | 'slow' | 'error' | 'empty'

export function createEmptyRepresentativeDemoState(): RepresentativeDemoState {
  return {
    records: {},
    waitingIds: [],
    activeIds: [],
    completedIds: [],
    openTabIds: [],
    selectedInteractionId: null,
  }
}

export async function loadRepresentativeDemoScenario(
  scenario: RepresentativeDemoScenario = 'default',
): Promise<RepresentativeDemoState> {
  if (scenario === 'slow') {
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  if (scenario === 'error') throw new Error('Synthetic repository unavailable')
  if (scenario === 'empty') return createEmptyRepresentativeDemoState()
  return createRepresentativeDemoState()
}
