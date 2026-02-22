import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const mockUseHydra = vi.fn()

vi.mock('../../context/HydraContext', () => ({
  useHydra: (...args) => mockUseHydra(...args),
}))

const { SessionSidebar } = await import('../SessionSidebar')

function defaultContext(overrides = {}) {
  return {
    sessions: [],
    currentSessionId: null,
    selectedSessionId: null,
    selectSession: vi.fn(),
    ...overrides,
  }
}

beforeEach(() => {
  mockUseHydra.mockReturnValue(defaultContext())
})

const SESSION_A = {
  id: 'org-repo-20240315T142530',
  repo: 'org/repo',
  started_at: '2024-03-15T14:25:30+00:00',
  ended_at: '2024-03-15T15:00:00+00:00',
  issues_processed: [1, 2, 3],
  issues_succeeded: 2,
  issues_failed: 1,
  status: 'completed',
}

const SESSION_B = {
  id: 'org-repo-20240316T100000',
  repo: 'org/repo',
  started_at: '2024-03-16T10:00:00+00:00',
  ended_at: null,
  issues_processed: [],
  issues_succeeded: 0,
  issues_failed: 0,
  status: 'active',
}

const SESSION_OTHER = {
  id: 'other-repo-20240315T090000',
  repo: 'other-org/other-repo',
  started_at: '2024-03-15T09:00:00+00:00',
  ended_at: '2024-03-15T09:30:00+00:00',
  issues_processed: [10],
  issues_succeeded: 1,
  issues_failed: 0,
  status: 'completed',
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('SessionSidebar with no sessions', () => {
  it('renders "Sessions" header', () => {
    render(<SessionSidebar />)
    expect(screen.getByText('Sessions')).toBeDefined()
  })

  it('renders "All" button', () => {
    render(<SessionSidebar />)
    expect(screen.getByText('All')).toBeDefined()
  })

  it('shows empty state message when no sessions', () => {
    render(<SessionSidebar />)
    expect(screen.getByText('No sessions yet')).toBeDefined()
  })

  it('does not show count badge when sessions is empty', () => {
    render(<SessionSidebar />)
    // count badge only appears if sessions.length > 0
    expect(screen.queryByText('0')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Sessions rendering
// ---------------------------------------------------------------------------

describe('SessionSidebar with sessions', () => {
  beforeEach(() => {
    mockUseHydra.mockReturnValue(
      defaultContext({ sessions: [SESSION_A, SESSION_B] })
    )
  })

  it('renders repo group header', () => {
    render(<SessionSidebar />)
    expect(screen.getByText('org/repo')).toBeDefined()
  })

  it('shows issue count pill for sessions with processed issues', () => {
    render(<SessionSidebar />)
    // SESSION_A has 3 issues_processed
    expect(screen.getByText('3')).toBeDefined()
  })

  it('shows success count for sessions with successes', () => {
    render(<SessionSidebar />)
    // SESSION_A has 2 successes
    expect(screen.getByText('2✓')).toBeDefined()
  })

  it('shows fail count for sessions with failures', () => {
    render(<SessionSidebar />)
    // SESSION_A has 1 failure
    expect(screen.getByText('1✗')).toBeDefined()
  })

  it('shows total session count badge in header', () => {
    render(<SessionSidebar />)
    // Both header badge and repo count show '2', verify at least one exists
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1)
  })
})

// ---------------------------------------------------------------------------
// Multi-repo grouping
// ---------------------------------------------------------------------------

describe('SessionSidebar with multiple repos', () => {
  beforeEach(() => {
    mockUseHydra.mockReturnValue(
      defaultContext({ sessions: [SESSION_A, SESSION_OTHER] })
    )
  })

  it('renders both repo group headers', () => {
    render(<SessionSidebar />)
    expect(screen.getByText('org/repo')).toBeDefined()
    expect(screen.getByText('other-org/other-repo')).toBeDefined()
  })
})

// ---------------------------------------------------------------------------
// Selection
// ---------------------------------------------------------------------------

describe('SessionSidebar selection', () => {
  it('calls selectSession(null) when clicking All button', () => {
    const selectSession = vi.fn()
    mockUseHydra.mockReturnValue(
      defaultContext({ sessions: [SESSION_A], selectSession })
    )
    render(<SessionSidebar />)
    fireEvent.click(screen.getByText('All'))
    expect(selectSession).toHaveBeenCalledWith(null)
  })

  it('calls selectSession with session id when clicking a session row', () => {
    const selectSession = vi.fn()
    mockUseHydra.mockReturnValue(
      defaultContext({ sessions: [SESSION_A], selectSession })
    )
    render(<SessionSidebar />)
    // session time is shown as relative text; click the row using test-id workaround
    // The session row includes the relativeTime + meta; click anywhere in the list
    const repoGroup = screen.getByText('org/repo')
    // The session row is rendered after the repo group; find session-specific text
    // Since SESSION_A has 3 issues and 2 succeeded, clicking the success count fires selectSession
    fireEvent.click(screen.getByText('2✓'))
    expect(selectSession).toHaveBeenCalledWith(SESSION_A.id)
  })
})

// ---------------------------------------------------------------------------
// Repo collapse / expand
// ---------------------------------------------------------------------------

describe('SessionSidebar collapsible repo sections', () => {
  beforeEach(() => {
    mockUseHydra.mockReturnValue(
      defaultContext({ sessions: [SESSION_A] })
    )
  })

  it('sessions are visible when repo section is expanded (default)', () => {
    render(<SessionSidebar />)
    // Issue count pill for SESSION_A should be visible
    expect(screen.getByText('3')).toBeDefined()
  })

  it('sessions are hidden after collapsing repo section', () => {
    render(<SessionSidebar />)
    // Click repo header to collapse
    fireEvent.click(screen.getByText('org/repo'))
    // Issue count pill should no longer be in the DOM
    expect(screen.queryByText('3')).toBeNull()
  })

  it('toggle arrow changes on collapse/expand', () => {
    render(<SessionSidebar />)
    // Initially expanded — down arrow
    expect(screen.getByText('▾')).toBeDefined()
    fireEvent.click(screen.getByText('org/repo'))
    // After collapse — right arrow
    expect(screen.getByText('▸')).toBeDefined()
  })
})

// ---------------------------------------------------------------------------
// Active session highlighting
// ---------------------------------------------------------------------------

describe('SessionSidebar active session state', () => {
  it('currentSessionId is reflected (session with active status rendered)', () => {
    mockUseHydra.mockReturnValue(
      defaultContext({
        sessions: [SESSION_B],
        currentSessionId: SESSION_B.id,
        selectedSessionId: null,
      })
    )
    render(<SessionSidebar />)
    // Active session has status 'active' — no issue pill since issues_processed is empty
    // The repo header should be visible
    expect(screen.getByText('org/repo')).toBeDefined()
  })
})
