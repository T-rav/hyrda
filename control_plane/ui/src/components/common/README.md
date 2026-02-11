# Control Plane UI - Common Components

A library of reusable, testable React components for the InsightMesh Control Plane UI.

## Components

### Button
Multi-variant button component with loading states and icons.

```jsx
import Button from './common/Button'

<Button variant="primary" onClick={handleClick}>
  Save
</Button>

<Button variant="danger" isLoading leftIcon={<Trash size={16} />}>
  Delete
</Button>
```

**Variants:** `primary`, `secondary`, `danger`, `success`, `ghost`, `link`
**Sizes:** `sm`, `md`, `lg`

### Modal
Accessible modal dialog with focus management and keyboard navigation.

```jsx
import Modal from './common/Modal'

<Modal
  isOpen={showModal}
  onClose={handleClose}
  title="Confirm Action"
  size="md"
  onConfirm={handleConfirm}
  confirmText="Delete"
  confirmVariant="danger"
>
  <p>Are you sure you want to delete this item?</p>
</Modal>
```

**Sizes:** `sm`, `md`, `lg`, `xl`, `full`

### Input
Form input with label, error handling, and icons.

```jsx
import Input from './common/Input'

<Input
  label="Email"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  error={errors.email}
  leftIcon={<Mail size={16} />}
  required
/>
```

### Textarea
Multi-line text input with resize control.

```jsx
import Textarea from './common/Textarea'

<Textarea
  label="Description"
  value={description}
  onChange={(e) => setDescription(e.target.value)}
  rows={4}
  hint="Maximum 500 characters"
/>
```

### Select
Dropdown select with options.

```jsx
import Select from './common/Select'

<Select
  label="Status"
  value={status}
  onChange={(e) => setStatus(e.target.value)}
  options={[
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' }
  ]}
/>
```

### Card
Container component with header, body, and footer sections.

```jsx
import Card from './common/Card'

<Card
  title="User Information"
  footer={<Button>Save</Button>}
  hoverable
>
  <p>Card content goes here</p>
</Card>
```

**Variants:** `default`, `outlined`, `ghost`

### Badge
Status indicator with multiple color variants.

```jsx
import Badge from './common/Badge'

<Badge variant="success" leftIcon={<Check size={12} />}>
  Active
</Badge>
```

**Variants:** `default`, `primary`, `secondary`, `success`, `danger`, `warning`, `info`, `outline`

### EmptyState
Display when no data is available.

```jsx
import EmptyState from './common/EmptyState'

<EmptyState
  title="No agents found"
  description="Get started by creating your first agent"
  actionLabel="Create Agent"
  onAction={handleCreate}
/>
```

### LoadingState
Loading indicator with optional fullscreen overlay.

```jsx
import LoadingState from './common/LoadingState'

<LoadingState message="Fetching data..." size="lg" />

// Fullscreen overlay
<LoadingState fullscreen message="Loading..." />
```

## Import Patterns

### Individual imports (Recommended)
```jsx
import Button from './common/Button'
import Modal from './common/Modal'
```

### Index import
```jsx
import { Button, Modal, Input } from './common'
```

## Testing

All components have comprehensive test coverage:

```bash
npm test
```

Tests cover:
- Rendering variations
- User interactions
- Accessibility attributes
- Error states
- Loading states

## CSS Classes

Components use BEM-inspired naming:
- `.btn` - Base button class
- `.btn-primary` - Primary variant
- `.btn-loading` - Loading state modifier
- `.modal-overlay` - Modal backdrop
- `.modal-content` - Modal container
- `.input-wrapper` - Input container
- `.input-error` - Error state

See `App.css` for complete styling definitions.
