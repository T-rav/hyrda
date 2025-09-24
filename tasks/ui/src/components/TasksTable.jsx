import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const statusStyles = {
  running: { class: 'bg-primary', icon: 'spinner' },
  success: { class: 'bg-success', icon: 'check' },
  failed: { class: 'bg-danger', icon: 'x' },
  cancelled: { class: 'bg-secondary', icon: 'ban' }
}

function TasksTable({ taskRuns, showAll, currentPage, recordsPerPage, onPageChange }) {
  if (!taskRuns || taskRuns.length === 0) {
    return (
      <div className="table-container">
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <p>No recent runs</p>
        </div>
      </div>
    )
  }

  // Calculate displayed runs
  let displayedRuns
  if (showAll) {
    const startIndex = (currentPage - 1) * recordsPerPage
    const endIndex = startIndex + recordsPerPage
    displayedRuns = taskRuns.slice(startIndex, endIndex)
  } else {
    displayedRuns = taskRuns.slice(0, 5)
  }

  // Pagination info
  const totalPages = Math.ceil(taskRuns.length / recordsPerPage)
  const startRecord = (currentPage - 1) * recordsPerPage + 1
  const endRecord = Math.min(currentPage * recordsPerPage, taskRuns.length)

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (run) => {
    if (run.duration_seconds) {
      return `${run.duration_seconds.toFixed(1)}s`
    }
    return run.status === 'running' ? 'Running...' : 'N/A'
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Started</th>
            <th>Status</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {displayedRuns.map((run, index) => {
            const statusStyle = statusStyles[run.status] || statusStyles.cancelled

            return (
              <tr key={index}>
                <td>
                  <div className="task-name">
                    <strong>{run.job_name || 'Unknown Job'}</strong>
                    {run.triggered_by === 'manual' && (
                      <span className="badge bg-info ms-2">Manual</span>
                    )}
                  </div>
                </td>
                <td>{formatDate(run.started_at)}</td>
                <td>
                  <span className={`badge ${statusStyle.class}`}>
                    {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                  </span>
                </td>
                <td>
                  <div className="task-details">
                    <small className="text-muted">
                      {formatDuration(run)}
                      {run.records_processed && ` • ${run.records_processed} records`}
                    </small>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Pagination Controls */}
      {showAll && totalPages > 1 && (
        <div className="pagination-controls">
          <div className="pagination-info">
            <span className="text-muted">
              Showing {startRecord}-{endRecord} of {taskRuns.length} runs
            </span>
          </div>
          <nav className="pagination-nav">
            <button
              className={`btn btn-sm btn-outline-secondary ${currentPage === 1 ? 'disabled' : ''}`}
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            {/* Page numbers */}
            <div className="page-numbers">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const startPage = Math.max(1, currentPage - 2)
                const pageNum = startPage + i
                if (pageNum > totalPages) return null

                return (
                  <button
                    key={pageNum}
                    className={`btn btn-sm ${
                      pageNum === currentPage ? 'btn-primary' : 'btn-outline-secondary'
                    }`}
                    onClick={() => onPageChange(pageNum)}
                  >
                    {pageNum}
                  </button>
                )
              })}
            </div>

            <button
              className={`btn btn-sm btn-outline-secondary ${
                currentPage === totalPages ? 'disabled' : ''
              }`}
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight size={16} />
            </button>
          </nav>
        </div>
      )}
    </div>
  )
}

export default TasksTable
