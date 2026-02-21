/**
 * @typedef {'batch_start'|'phase_change'|'worker_update'|'transcript_line'|'pr_created'|'review_update'|'merge_update'|'batch_complete'|'error'} EventType
 *
 * @typedef {{ type: EventType, timestamp: string, data: Record<string, any> }} HydraEvent
 *
 * @typedef {'queued'|'planning'|'running'|'testing'|'committing'|'quality_fix'|'reviewing'|'done'|'failed'} WorkerStatus
 *
 * @typedef {{ status: WorkerStatus, worker: number, role: string, title: string, branch: string, transcript: string[], pr: object|null }} WorkerState
 *
 * @typedef {{ pr: number, issue: number, branch: string, draft: boolean, url: string }} PRData
 *
 * @typedef {{ pr: number, verdict: string, summary: string, duration?: number }} ReviewData
 *
 * @typedef {{ issue: number, title: string, issueUrl: string, pr: number, prUrl: string, branch: string, cause: string, status: string }} HITLItem
 *
 * @typedef {Record<string, string>} HumanInputRequests
 *
 * @typedef {{ issue: number, title: string, url: string, status: string, pr: number, prUrl: string, labels: string[] }} IssueListItem
 *
 * @typedef {{ name: string, status: string, last_run: string|null, details: Record<string, any> }} BackgroundWorkerState
 *
 * @typedef {{ lifetime: { issues_completed: number, prs_merged: number, issues_created: number }, rates: Record<string, number> }} MetricsData
 */

export {}
