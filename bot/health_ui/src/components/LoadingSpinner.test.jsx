import { render, screen } from '@testing-library/react'
import LoadingSpinner from './LoadingSpinner'

describe('LoadingSpinner', () => {
  test('renders loading spinner', () => {
    render(<LoadingSpinner />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  test('has correct CSS classes for styling', () => {
    const { container } = render(<LoadingSpinner />)

    const loadingDiv = container.querySelector('.loading')
    expect(loadingDiv).toBeInTheDocument()
  })

  test('displays loading icon', () => {
    render(<LoadingSpinner />)

    // Check for the presence of an SVG (lucide-react icons render as SVG)
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
