import { theme } from './theme'

/**
 * Statuses that indicate a worker is actively processing.
 * Used across dashboard components to filter/count active workers.
 */
export const ACTIVE_STATUSES = [
  'running', 'testing', 'committing', 'reviewing', 'planning', 'quality_fix',
  'start', 'merge_main', 'merge_fix', 'ci_wait', 'ci_fix', 'merging',
  'evaluating', 'validating', 'retrying', 'fixing',
]

/** Maximum number of events retained in the frontend event buffer. */
export const MAX_EVENTS = 5000

/**
 * Canonical pipeline stage definitions.
 * All stage metadata lives here to prevent drift across components.
 * Components derive their own views (uppercase labels, filtered subsets, etc.) from this array.
 */
export const PIPELINE_STAGES = [
  { key: 'triage',    label: 'Triage',    color: theme.triageGreen, subtleColor: theme.greenSubtle,  role: 'triage',      configKey: null },
  { key: 'plan',      label: 'Plan',      color: theme.purple,      subtleColor: theme.purpleSubtle, role: 'planner',     configKey: 'max_planners' },
  { key: 'implement', label: 'Implement', color: theme.accent,      subtleColor: theme.accentSubtle, role: 'implementer', configKey: 'max_workers' },
  { key: 'review',    label: 'Review',    color: theme.orange,      subtleColor: theme.orangeSubtle, role: 'reviewer',    configKey: 'max_reviewers' },
  { key: 'merged',    label: 'Merged',    color: theme.green,       subtleColor: theme.greenSubtle,  role: null,           configKey: null },
]

/** Valid overall statuses for stream cards. */
export const STREAM_CARD_STATUSES = ['active', 'done', 'failed', 'hitl']

/**
 * Pipeline loop definitions — core processing loops that can be toggled on/off.
 */
export const PIPELINE_LOOPS = [
  { key: 'triage',    label: 'Triage',    color: theme.triageGreen, dimColor: theme.greenSubtle },
  { key: 'plan',      label: 'Plan',      color: theme.purple,      dimColor: theme.purpleSubtle },
  { key: 'implement', label: 'Implement', color: theme.accent,      dimColor: theme.accentSubtle },
  { key: 'review',    label: 'Review',    color: theme.orange,      dimColor: theme.orangeSubtle },
]

/**
 * Background worker definitions — maintenance and system loops that can be toggled on/off.
 * Workers with `system: true` are internal services shown with a "system" badge.
 */
export const BACKGROUND_WORKERS = [
  { key: 'retrospective',   label: 'Retrospective',   color: theme.purple },
  { key: 'review_insights', label: 'Review Insights',  color: theme.orange },
  { key: 'pipeline_poller', label: 'Pipeline Poller',  color: theme.textMuted, system: true },
  { key: 'memory_sync',     label: 'Memory Sync',      color: theme.accent,    system: true },
  { key: 'metrics',         label: 'Metrics',           color: theme.yellow,    system: true },
]
