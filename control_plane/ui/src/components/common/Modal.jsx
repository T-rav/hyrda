import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import Button from './Button'

/**
 * Reusable Modal component with Bootstrap-style classes
 *
 * @typedef {Object} ModalProps
 * @property {boolean} isOpen - Whether the modal is visible
 * @property {Function} onClose - Callback when modal should close
 * @property {string} title - Modal header title
 * @property {React.ReactNode} children - Modal content
 * @property {React.ReactNode} [footer] - Custom footer content
 * @property {string} [size='md'] - Modal size (sm, md, lg, xl, full)
 * @property {boolean} [showCloseButton=true] - Show close button in header
 * @property {boolean} [closeOnOverlayClick=true] - Close when clicking overlay
 * @property {boolean} [closeOnEsc=true] - Close when pressing Escape
 * @property {string} [className] - Additional CSS classes for content
 * @property {boolean} [isLoading=false] - Show loading state in footer
 * @property {Function} [onConfirm] - Confirm action handler
 * @property {string} [confirmText='Confirm'] - Confirm button text
 * @property {string} [confirmVariant='primary'] - Confirm button variant
 * @property {string} [cancelText='Cancel'] - Cancel button text
 * @property {boolean} [hideDefaultFooter=false] - Hide default footer buttons
 */

const SIZES = {
  sm: 'modal-sm',
  md: '',
  lg: 'modal-lg',
  xl: 'modal-xl',
  full: 'modal-full',
}

function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  showCloseButton = true,
  closeOnOverlayClick = true,
  closeOnEsc = true,
  className = '',
  isLoading = false,
  onConfirm,
  confirmText = 'Confirm',
  confirmVariant = 'secondary',
  cancelText = 'Cancel',
  hideDefaultFooter = false,
}) {
  const contentRef = useRef(null)
  const previousActiveElement = useRef(null)

  // Handle escape key
  useEffect(() => {
    if (!isOpen || !closeOnEsc) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, closeOnEsc, onClose])

  // Handle body scroll lock and focus management
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement
      document.body.style.overflow = 'hidden'
      if (contentRef.current) {
        contentRef.current.focus()
      }
    } else {
      document.body.style.overflow = ''
      if (previousActiveElement.current) {
        previousActiveElement.current.focus()
      }
    }

    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Handle overlay click
  const handleOverlayClick = (e) => {
    if (closeOnOverlayClick && e.target === e.currentTarget) {
      onClose()
    }
  }

  if (!isOpen) return null

  const sizeClass = SIZES[size] || ''
  const contentClasses = ['modal-content', sizeClass, className]
    .filter(Boolean)
    .join(' ')

  const showDefaultFooter = !hideDefaultFooter && onConfirm

  return (
    <div
      className="modal-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={contentRef}
        className={contentClasses}
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        <div className="modal-header">
          <h5 id="modal-title" className="modal-title">
            {title}
          </h5>
          {showCloseButton && (
            <button
              type="button"
              className="modal-close"
              onClick={onClose}
              aria-label="Close"
            >
              <X size={20} />
            </button>
          )}
        </div>

        <div className="modal-body" role="region" aria-label="Modal content">
          {children}
        </div>

        {(showDefaultFooter || footer) && (
          <div className="modal-footer">
            {footer || (
              <>
                <Button
                  variant="secondary"
                  onClick={onClose}
                  disabled={isLoading}
                >
                  {cancelText}
                </Button>
                <Button
                  variant={confirmVariant}
                  onClick={onConfirm}
                  isLoading={isLoading}
                >
                  {confirmText}
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default Modal
