# Plan for Issue #23

## Issue Restatement

Several React components create new style objects inline via object spread inside `.map()` loops. This means N new objects per render for list components. The fix is to pre-compute style variants at module scope (for styles derived from finite, known value sets) so that the same object reference is reused across renders.

## Files to Modify

### 1. `ui/src/components/EventLog.jsx`
**Problem (line 46):** `style={{ ...styles.type, color: typeColors[e.type] || '#8b949e' }}` inside `.map()` — creates a new object per event per render.

**Fix:** Pre-compute a style object for each event type at module scope, after the `styles` const:
```jsx
// After styles definition:
const typeSpanStyles = Object.fromEntries(
  Object.entries(typeColors).map(([k, v]) => [k, { ...styles.type, color: v }])
)
const defaultTypeStyle = { ...styles.type, color: '#8b949e' }
```
Then on line 46 replace with:
```jsx
<span style={typeSpanStyles[e.type] || defaultTypeStyle}>
```

### 2. `ui/src/components/WorkerList.jsx`
**Problem (lines 103-105):** `style={{ ...styles.card, ...(isActive ? styles.active : {}) }}` — creates a new object per worker per render.
**Problem (line 113):** `style={{ ...styles.status, background: sc.bg, color: sc.fg }}` — creates a new object per worker per render.

**Fix:** Pre-compute at module scope after `styles`:
```jsx
// Card variants (only 2 possibilities)
const cardStyle = styles.card
const cardActiveStyle = { ...styles.card, ...styles.active }

// Status badge variants (one per known status)
const statusBadgeStyles = Object.fromEntries(
  Object.entries(statusColors).map(([k, v]) => [
    k, { ...styles.status, background: v.bg, color: v.fg }
  ])
)
```
Then replace:
- Line 103-105: `style={isActive ? cardActiveStyle : cardStyle}`
- Line 113: `style={statusBadgeStyles[w.status] || statusBadgeStyles.queued}`

### 3. `ui/src/components/PipelineStatus.jsx`
**Problem (lines 36-47):** Connector and stage styles spread inside `.map()` over STAGES (3 items).

**Fix:** Pre-compute per-stage active/inactive variants at module scope after `styles`:
```jsx
const connectorStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    active: { ...styles.connector, background: s.color },
    inactive: { ...styles.connector, background: '#30363d' },
  }])
)

const stageStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    active: { ...styles.stage, background: s.color, color: '#0d1117', borderColor: s.color },
    inactive: { ...styles.stage, background: '#21262d', color: '#484f58', borderColor: '#30363d' },
  }])
)
```
Then replace:
- Line 36-39: `style={connectorStyles[stage.key][isActive ? 'active' : 'inactive']}`
- Line 42-47: `style={stageStyles[stage.key][isActive ? 'active' : 'inactive']}`

### 4. `ui/src/components/Header.jsx`
**Problem (lines 40-43):** Connection dot style, 2 variants.
**Problem (lines 63-73):** Connector and pill styles inside `.map()` over STAGES (4 items).
**Problem (lines 87-89):** Start button style, 2 variants.

**Fix:** Pre-compute at module scope after `styles`:
```jsx
// Dot variants
const dotConnected = { ...styles.dot, background: '#3fb950' }
const dotDisconnected = { ...styles.dot, background: '#f85149' }

// Per-stage pill/connector variants
const pillStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.pill, background: s.color, color: '#0d1117', borderColor: s.color },
    dim: { ...styles.pill, background: '#21262d', color: '#484f58', borderColor: '#30363d' },
  }])
)

const headerConnectorStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.connector, background: s.color },
    dim: { ...styles.connector, background: '#30363d' },
  }])
)

// Start button variants
const startBtnEnabled = { ...styles.startBtn, opacity: 1, cursor: 'pointer' }
const startBtnDisabled = { ...styles.startBtn, opacity: 0.4, cursor: 'not-allowed' }
```
Then replace:
- Line 40-43: `style={connected ? dotConnected : dotDisconnected}`
- Line 63-66: `style={headerConnectorStyles[stage.key][lit ? 'lit' : 'dim']}`
- Line 68-73: `style={pillStyles[stage.key][lit ? 'lit' : 'dim']}`
- Line 87-89: `style={connected ? startBtnEnabled : startBtnDisabled}`

### 5. `ui/src/App.jsx`
**Problem (lines 74-77):** Tab styles inside `.map()` over TABS (4 items).

**Fix:** Pre-compute at module scope after `styles`:
```jsx
const tabInactiveStyle = styles.tab
const tabActiveStyle = { ...styles.tab, ...styles.tabActive }
```
Then replace line 74-77:
```jsx
style={activeTab === tab ? tabActiveStyle : tabInactiveStyle}
```

## New Files

None needed.

## Implementation Steps

1. **EventLog.jsx** — Add `typeSpanStyles` and `defaultTypeStyle` after the `styles` const. Replace the inline spread on line 46 with a lookup.

2. **WorkerList.jsx** — Add `cardStyle`, `cardActiveStyle`, and `statusBadgeStyles` after the `styles` const. Replace inline spreads on lines 103-105 and 113.

3. **PipelineStatus.jsx** — Add `connectorStyles` and `stageStyles` after the `styles` const. Replace inline spreads on lines 36-39 and 42-47.

4. **Header.jsx** — Add `dotConnected`, `dotDisconnected`, `pillStyles`, `headerConnectorStyles`, `startBtnEnabled`, `startBtnDisabled` after the `styles` const. Replace all inline spreads.

5. **App.jsx** — Add `tabActiveStyle` and `tabInactiveStyle` after the `styles` const. Replace the inline spread on lines 74-77.

6. **Verify the build** — Run `make ui` (or `npm run build` in `ui/`) to ensure no syntax errors.

## Testing Strategy

There is no existing frontend test infrastructure (no vitest/jest configured, no test files). The changes are purely mechanical — moving style computation from render-time to module-scope with identical resulting objects. Testing approach:

1. **Set up vitest** — Add `vitest` and `@testing-library/react` as devDependencies in `ui/package.json`. Add a `test` script. Add a `vitest.config.js` (or extend `vite.config.js`).

2. **Write unit tests for pre-computed style maps** to verify:
   - `typeSpanStyles` has an entry for every key in `typeColors`, each including `fontWeight: 600` (from base style) and the correct `color`
   - `defaultTypeStyle` has `color: '#8b949e'`
   - `statusBadgeStyles` has an entry for every key in `statusColors` with correct `background` and `color`
   - `cardActiveStyle` includes properties from both `styles.card` and `styles.active`
   - `connectorStyles`/`stageStyles` have entries for each stage with `active`/`inactive` sub-keys
   - `pillStyles`/`headerConnectorStyles` have entries for each stage
   - `tabActiveStyle` includes properties from both `styles.tab` and `styles.tabActive`

3. **Write smoke render tests** for each component to ensure they render without errors with representative props (using `@testing-library/react`'s `render()`).

## Key Considerations

- **All components use function declarations** (not arrow function `const`s), so they are hoisted. Pre-computed variants defined after the `styles` const at module bottom will be initialized before any component renders.
- **No behavioral change** — the rendered output is identical; only object identity changes (same reference reused instead of new object per render).
- **Finite value sets** — All dynamic values (`typeColors`, `statusColors`, `STAGES`, tab variants, active/inactive) come from finite, module-level constants, making full pre-computation possible without `useMemo`.
- **No `useMemo` needed** — Since all variants can be derived from static data, module-scope pre-computation is simpler and avoids hook overhead.
- **Backward compatibility** — No API or prop changes. Drop-in replacement.

---
**Summary:** Pre-compute all inline style object spreads at module scope using lookup maps derived from existing finite constant sets (typeColors, statusColors, STAGES, etc.) to eliminate per-render object allocations in list components.
