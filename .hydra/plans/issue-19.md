# Plan for Issue #19

## Goal

Extract inline style objects from `mdComponents` component functions in `TranscriptView.jsx` to module-level constants, eliminating unnecessary object allocations on every render.

## Files to Modify

### `ui/src/components/TranscriptView.jsx`

**Change 1: Add `mdStyles` constant** (insert before `mdComponents`, around line 73)

```jsx
const mdStyles = {
  h1: { fontSize: 16, fontWeight: 700, color: '#e6edf3', margin: '8px 0 4px' },
  h2: { fontSize: 14, fontWeight: 700, color: '#e6edf3', margin: '6px 0 3px' },
  h3: { fontSize: 13, fontWeight: 600, color: '#e6edf3', margin: '4px 0 2px' },
  inlineCode: { background: '#161b22', padding: '2px 5px', borderRadius: 4, fontSize: 11, color: '#79c0ff' },
  pre: { background: '#161b22', padding: 8, borderRadius: 6, overflowX: 'auto', fontSize: 11, lineHeight: 1.5, margin: '4px 0' },
  codeBlock: { color: '#e6edf3' },
  ul: { margin: '2px 0', paddingLeft: 20 },
  ol: { margin: '2px 0', paddingLeft: 20 },
  li: { margin: '1px 0' },
  strong: { color: '#e6edf3' },
  p: { margin: '2px 0' },
}
```

**Change 2: Update `mdComponents` to reference `mdStyles`** (replace lines 73-86)

```jsx
const mdComponents = {
  h1: ({ children }) => <h1 style={mdStyles.h1}>{children}</h1>,
  h2: ({ children }) => <h2 style={mdStyles.h2}>{children}</h2>,
  h3: ({ children }) => <h3 style={mdStyles.h3}>{children}</h3>,
  code: ({ inline, children }) =>
    inline
      ? <code style={mdStyles.inlineCode}>{children}</code>
      : <pre style={mdStyles.pre}><code style={mdStyles.codeBlock}>{children}</code></pre>,
  ul: ({ children }) => <ul style={mdStyles.ul}>{children}</ul>,
  ol: ({ children }) => <ol style={mdStyles.ol}>{children}</ol>,
  li: ({ children }) => <li style={mdStyles.li}>{children}</li>,
  strong: ({ children }) => <strong style={mdStyles.strong}>{children}</strong>,
  p: ({ children }) => <p style={mdStyles.p}>{children}</p>,
}
```

## New Files

None.

## Implementation Steps

1. Add the `mdStyles` constant object before the existing `mdComponents` definition (after line 71, before current line 73).
2. Replace the `mdComponents` definition (lines 73-86) to reference `mdStyles.<key>` instead of inline object literals.
3. Run `cd ui && npx vite build` to verify no syntax errors.
4. Visually verify in the dashboard that markdown rendering is unchanged (headings, code blocks, lists, bold, paragraphs all render correctly).

## Testing Strategy

- **No frontend test framework exists** in the UI project (no vitest/jest configured), so no unit tests can be added for this change.
- This is a **pure mechanical refactor** — same style values, just moved to stable references. Zero behavioral change.
- **Build verification**: `vite build` confirms the JSX compiles without errors.
- **Manual smoke test**: Open the dashboard, select a worker with transcript output, and verify markdown elements (headings, code, lists, bold, paragraphs) render with correct styling.

## Key Considerations

- **Backward compatibility**: Fully backward compatible — same styles, same components, same props. Only object identity changes (stable references instead of ephemeral ones).
- **Edge cases**: The `code` component has a conditional (`inline` vs block) — both branches now reference `mdStyles` properties. No logic change.
- **Performance impact**: Eliminates N×M object allocations per render (N transcript lines × M markdown elements per line). Style objects are now created once at module load.
- **Naming**: Using `mdStyles` to parallel the existing `mdComponents` naming pattern. The `code` element needs two keys (`inlineCode` and `pre`/`codeBlock`) since it has two style variants.

---
**Summary:** Extract inline style objects from mdComponents to a module-level mdStyles constant to eliminate per-render object allocations.
