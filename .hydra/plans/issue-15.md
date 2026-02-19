# Plan for Issue #15

## Issue Summary

The `inputDot` style in `WorkerList.jsx` (line 179) references `animation: 'pulse 1.5s ease-in-out infinite'`, but no `@keyframes pulse` animation is defined anywhere in the codebase. Since the entire UI uses inline styles (no CSS files), the named CSS keyframes animation cannot resolve, and the dot renders statically instead of pulsing.

## Files to Modify

### 1. `ui/src/components/WorkerList.jsx`
- Inject a `<style>` element defining the `@keyframes pulse` animation
- This keeps the animation co-located with the component that uses it, consistent with the project's inline-styles approach

### 2. `ui/index.html` — **No changes needed**
- While adding the keyframes here would work, it would separate the animation definition from its only consumer. Better to keep it in the component.

## New Files

None required.

## Implementation Steps

### Step 1: Add keyframes injection to `WorkerList.jsx`

Add a `@keyframes pulse` definition by injecting a `<style>` tag at the top of the `WorkerList` component's render output. The approach:

1. At the top of the file, add a `useEffect` import (already imported: `useState` — add `useEffect`).
2. Inside the `WorkerList` component, use a `useEffect` to inject a `<style>` element into `document.head` on mount, and remove it on unmount. This ensures the keyframes are available when the component renders.

Alternatively (simpler approach): render a `<style>` JSX element directly in the component output. This is the simplest pattern and avoids lifecycle complexity:

```jsx
export function WorkerList({ workers, selectedWorker, onSelect, humanInputRequests = {} }) {
  // ... existing code ...
  return (
    <div style={styles.sidebar}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
      {/* ... existing RoleSection components ... */}
    </div>
  )
}
```

The pulse animation should smoothly fade the amber dot between full opacity and reduced opacity, creating a clear "attention needed" visual indicator.

### Step 2: Verify the animation works

Open the dashboard, trigger a human-input-required state for a worker, and confirm the amber dot next to the issue number pulses smoothly.

## Testing Strategy

The project currently has no frontend test infrastructure (no test files in `ui/src/`, no test runner configured for the UI). Given this is a purely visual CSS fix:

1. **Manual verification**: Load the dashboard, ensure a worker has `hasPendingInput` true, and verify the dot pulses.
2. **No new automated test required**: This is a CSS keyframes definition — there's no logic to unit test. The existing inline style reference (`animation: 'pulse 1.5s ease-in-out infinite'`) is already correct; it just needs the keyframes to exist.
3. **If a frontend test framework is later added**: A test could verify that the `<style>` element containing `@keyframes pulse` is rendered when `WorkerList` mounts.

## Key Considerations

- **Idempotency**: Using a `<style>` JSX element inside the component is safe — React will manage it in the DOM. If multiple `WorkerList` instances mounted (unlikely given the layout), duplicate `<style>` tags are harmless for keyframes.
- **No CSS-in-JS library needed**: The inline `<style>` tag approach is the lightest-weight solution that fits the project's existing pattern of no external CSS files.
- **Animation values**: `opacity: 0.4` at 50% creates a noticeable but not jarring pulse. This can be tuned if desired.
- **Backward compatibility**: No existing behavior changes. The dot currently renders as a static amber circle; it will now pulse as originally intended.

---
**Summary:** Add `@keyframes pulse` definition via inline `<style>` tag in WorkerList component to fix the non-functional pulsing dot animation.
