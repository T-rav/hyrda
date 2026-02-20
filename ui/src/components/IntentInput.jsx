import React, { useState } from 'react'
import { theme } from '../theme'

export function IntentInput({ onSubmit }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    setLoading(true)
    try {
      await onSubmit(trimmed)
      setText('')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div style={styles.container}>
      <input
        style={styles.input}
        type="text"
        placeholder="What do you want to build?"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <button
        style={text.trim() && !loading ? styles.button : styles.buttonDisabled}
        onClick={handleSubmit}
        disabled={!text.trim() || loading}
      >
        {loading ? 'Creating...' : 'Send'}
      </button>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    padding: '12px 16px',
    gap: 10,
    borderBottom: `1px solid ${theme.border}`,
    background: theme.surface,
  },
  input: {
    flex: 1,
    padding: '10px 14px',
    background: theme.bg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    color: theme.text,
    fontFamily: 'inherit',
    fontSize: 13,
    outline: 'none',
  },
  button: {
    padding: '10px 20px',
    background: theme.accent,
    color: theme.white,
    border: 'none',
    borderRadius: 8,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 13,
  },
  buttonDisabled: {
    padding: '10px 20px',
    background: theme.mutedSubtle,
    color: theme.textMuted,
    border: 'none',
    borderRadius: 8,
    fontWeight: 600,
    cursor: 'default',
    fontFamily: 'inherit',
    fontSize: 13,
  },
}

// Pre-computed style exports for testing
export const inputContainerStyle = styles.container
export const inputButtonStyle = styles.button
export const inputButtonDisabledStyle = styles.buttonDisabled
