/**
 * @typedef {'batch_start'|'phase_change'|'worker_update'|'transcript_line'|'pr_created'|'review_update'|'merge_update'|'batch_complete'|'error'} EventType
 *
 * @typedef {{ type: EventType, timestamp: string, data: Record<string, any> }} HydraEvent
 *
 * @typedef {'queued'|'running'|'testing'|'committing'|'done'|'failed'} WorkerStatus
 *
 * @typedef {{ status: WorkerStatus, worker: number, title: string, branch: string, transcript: string[], pr: object|null }} WorkerState
 *
 * @typedef {{ pr: number, issue: number, branch: string, draft: boolean, url: string }} PRData
 *
 * @typedef {{ pr: number, verdict: string, summary: string, duration?: number }} ReviewData
 *
 * @typedef {{ issue: number, title: string, issueUrl: string, pr: number, prUrl: string, branch: string }} HITLItem
 *
 * @typedef {Record<string, string>} HumanInputRequests
 */

export {}
