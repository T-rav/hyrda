# Plan for Issue #29

## Issue Summary

Replace all hardcoded hex color values across `ui/index.html` and 9 React component files with CSS custom properties (defined in `:root`) and a shared `theme.js` constants module. The legacy `templates/index.html` already uses CSS variables — this brings the React app into parity.

---

## Color Inventory

### Base colors (10 from issue + 9 discovered)

| Variable | Hex | Used in |
|----------|-----|---------|
| `--bg` | `#0d1117` | index.html, Header, HumanInputBanner, PipelineStatus |
| `--surface` | `#161b22` | App, Header, WorkerList, EventLog, TranscriptView |
| `--border` | `#30363d` | App, Header, WorkerList, TranscriptView, PRTable, EventLog, HumanInputBanner, HITLTable, ReviewTable, PipelineStatus |
| `--text` | `#c9d1d9` | Header, WorkerList, HumanInputBanner, HITLTable, ReviewTable |
| `--text-muted` | `#8b949e` | App, Header, WorkerList, TranscriptView, PRTable, EventLog, HITLTable, ReviewTable |
| `--accent` | `#58a6ff` | App, Header, WorkerList, TranscriptView, PRTable, EventLog, HITLTable |
| `--green` | `#3fb950` | Header, WorkerList, PRTable, EventLog, ReviewTable |
| `--red` | `#f85149` | Header, WorkerList, EventLog, HITLTable, ReviewTable |
| `--yellow` | `#d29922` | Header, WorkerList, EventLog, HumanInputBanner, ReviewTable, PipelineStatus |
| `--orange` | `#d18616` | Header, WorkerList, EventLog, PipelineStatus |
| `--purple` | `#a371f7` | Header, WorkerList, TranscriptView, PipelineStatus |
| `--triage-green` | `#39d353` | Header (STAGES triage color) |
| `--surface-inset` | `#21262d` | Header, HITLTable, PipelineStatus (inactive pill bg) |
| `--text-inactive` | `#484f58` | Header, PipelineStatus (inactive pill text) |
| `--btn-green` | `#238636` | Header (start button) |
| `--btn-red` | `#da3633` | Header (stop button) |
| `--white` | `#ffffff` | Header (button text) |
| `--text-bright` | `#e6edf3` | TranscriptView (markdown headings, code blocks) |
| `--code-text` | `#79c0ff` | TranscriptView (inline code color) |

### Alpha/rgba variants

| Variable | Value | Used in |
|----------|-------|---------|
| `--accent-hover` | `rgba(88,166,255,0.08)` | WorkerList (active card bg) |
| `--accent-subtle` | `rgba(88,166,255,0.15)` | WorkerList (running status bg) |
| `--muted-subtle` | `rgba(139,148,158,0.15)` | WorkerList (queued status bg) |
| `--purple-subtle` | `rgba(163,113,247,0.15)` | WorkerList (planning status bg) |
| `--yellow-subtle` | `rgba(210,153,34,0.15)` | WorkerList (testing status bg), HumanInputBanner |
| `--orange-subtle` | `rgba(210,134,22,0.15)` | WorkerList (committing status bg) |
| `--green-subtle` | `rgba(63,185,80,0.15)` | WorkerList (done status bg) |
| `--red-subtle` | `rgba(248,81,73,0.15)` | WorkerList (failed status bg) |
| `--overlay` | `rgba(0,0,0,0.3)` | Header, PipelineStatus (count badge bg) |

---

## New Files

### `ui/src/theme.js`

A single-file module exporting CSS variable references as JS string constants for use in inline React styles.

```js
/**
 * Theme constants — CSS variable references for inline styles.
 * Actual color values are defined as :root custom properties in index.html.
 */
export const theme = {
  // Backgrounds
  bg: 'var(--bg)',
  surface: 'var(--surface)',
  surfaceInset: 'var(--surface-inset)',
  border: 'var(--border)',

  // Text
  text: 'var(--text)',
  textBright: 'var(--text-bright)',
  textMuted: 'var(--text-muted)',
  textInactive: 'var(--text-inactive)',

  // Semantic colors
  accent: 'var(--accent)',
  green: 'var(--green)',
  red: 'var(--red)',
  yellow: 'var(--yellow)',
  orange: 'var(--orange)',
  purple: 'var(--purple)',
  triageGreen: 'var(--triage-green)',

  // Buttons
  btnGreen: 'var(--btn-green)',
  btnRed: 'var(--btn-red)',
  white: 'var(--white)',

  // Code
  codeText: 'var(--code-text)',

  // Alpha variants (subtle backgrounds)
  accentHover: 'var(--accent-hover)',
  accentSubtle: 'var(--accent-subtle)',
  mutedSubtle: 'var(--muted-subtle)',
  purpleSubtle: 'var(--purple-subtle)',
  yellowSubtle: 'var(--yellow-subtle)',
  orangeSubtle: 'var(--orange-subtle)',
  greenSubtle: 'var(--green-subtle)',
  redSubtle: 'var(--red-subtle)',
  overlay: 'var(--overlay)',
}
```

---

## Files to Modify

### 1. `ui/index.html`

**What**: Add `:root` CSS custom properties block, update `body` styles to use variables.

**Changes**:
- Add `:root { ... }` block with all 19 base + 9 alpha variables listed above
- Change `background: #0d1117` → `background: var(--bg)`
- Change `color: #c9d1d9` → `color: var(--text)`

### 2. `ui/src/App.jsx`

**What**: Import `theme` from `./theme`, replace all hardcoded colors in `styles` object.

**Replacements**:
- `'#30363d'` → `theme.border` (2 occurrences: tabs borderBottom, timelineItem borderBottom)
- `'#161b22'` → `theme.surface` (tabs background)
- `'#8b949e'` → `theme.textMuted` (tab color, timelineTime color)
- `'#58a6ff'` → `theme.accent` (tabActive color/borderBottomColor, timelineType color)

### 3. `ui/src/components/Header.jsx`

**What**: Import `theme`, replace all hardcoded colors in STAGES array and `styles` object.

**Replacements in STAGES**:
- `'#39d353'` → `theme.triageGreen`
- `'#a371f7'` → `theme.purple`
- `'#58a6ff'` → `theme.accent`
- `'#d18616'` → `theme.orange`

**Replacements in JSX (dynamic styles)**:
- `'#3fb950'` → `theme.green` (connected dot)
- `'#f85149'` → `theme.red` (disconnected dot)
- `'#30363d'` → `theme.border` (inactive connector/border)
- `'#21262d'` → `theme.surfaceInset` (inactive pill bg)
- `'#0d1117'` → `theme.bg` (active pill text)
- `'#484f58'` → `theme.textInactive` (inactive pill text)

**Replacements in styles object**:
- `'#161b22'` → `theme.surface` (header bg)
- `'#30363d'` → `theme.border` (header borderBottom, sessionBox border)
- `'#58a6ff'` → `theme.accent` (logo color)
- `'#8b949e'` → `theme.textMuted` (subtitle, sessionLabel, stat)
- `'#0d1117'` → `theme.bg` (sessionBox bg)
- `'#c9d1d9'` → `theme.text` (statVal)
- `'#238636'` → `theme.btnGreen` (startBtn)
- `'#ffffff'` → `theme.white` (startBtn/stopBtn text)
- `'#da3633'` → `theme.btnRed` (stopBtn)
- `'#d29922'` → `theme.yellow` (stoppingBadge)
- `'#0d1117'` → `theme.bg` (stoppingBadge text)

### 4. `ui/src/components/WorkerList.jsx`

**What**: Import `theme`, replace all hardcoded colors in `statusColors` map and `styles` object.

**Replacements in statusColors**:
- All `fg` values → corresponding `theme.*` references
- All `bg` (rgba) values → corresponding `theme.*Subtle` references

**Replacements in styles object**:
- `'#30363d'` → `theme.border` (sidebar borderRight, card borderBottom)
- `'#161b22'` → `theme.surface` (sidebar bg)
- `'#8b949e'` → `theme.textMuted` (title, empty, chevron, sectionLabel, cardTitle, meta)
- `'#58a6ff'` → `theme.accent` (sectionCount, active borderLeft)
- `'rgba(88,166,255,0.08)'` → `theme.accentHover` (active bg)
- `'#c9d1d9'` → `theme.text` (issue)
- `'#d29922'` → `theme.yellow` (inputDot)

### 5. `ui/src/components/TranscriptView.jsx`

**What**: Import `theme`, replace all hardcoded colors in `mdComponents` and `styles` object.

**Replacements in mdComponents**:
- `'#e6edf3'` → `theme.textBright` (h1, h2, h3, strong, code block text)
- `'#161b22'` → `theme.surface` (inline code bg, code block bg)
- `'#79c0ff'` → `theme.codeText` (inline code text)

**Replacements in styles object**:
- `'#8b949e'` → `theme.textMuted` (empty, waiting, branch, lines)
- `'#30363d'` → `theme.border` (header borderBottom)
- `'#58a6ff'` → `theme.accent` (label, linePrefix)
- `'#a371f7'` → `theme.purple` (role color)

### 6. `ui/src/components/PRTable.jsx`

**What**: Import `theme`, replace all hardcoded colors.

**Replacements**:
- `'#8b949e'` → `theme.textMuted` (empty, th)
- `'#30363d'` → `theme.border` (th/td borderBottom)
- `'#58a6ff'` → `theme.accent` (link)
- `'#3fb950'` → `theme.green` (merged)

### 7. `ui/src/components/EventLog.jsx`

**What**: Import `theme`, replace all hardcoded colors in `typeColors` map and `styles` object.

**Replacements in typeColors**:
- `'#58a6ff'` → `theme.accent` (worker_update, batch_start)
- `'#d29922'` → `theme.yellow` (phase_change)
- `'#3fb950'` → `theme.green` (pr_created, merge_update, batch_complete)
- `'#d18616'` → `theme.orange` (review_update)
- `'#f85149'` → `theme.red` (error)
- `'#8b949e'` → `theme.textMuted` (transcript_line, fallback)

**Replacements in styles**:
- `'#30363d'` → `theme.border` (panel borderLeft, item borderBottom)
- `'#161b22'` → `theme.surface` (panel bg)
- `'#8b949e'` → `theme.textMuted` (title, empty, time)

### 8. `ui/src/components/HumanInputBanner.jsx`

**What**: Import `theme`, replace all hardcoded colors.

**Replacements**:
- `'rgba(210,153,34,0.15)'` → `theme.yellowSubtle` (banner bg)
- `'#d29922'` → `theme.yellow` (banner borderBottom, question, button bg)
- `'#0d1117'` → `theme.bg` (input bg, button text)
- `'#30363d'` → `theme.border` (input border)
- `'#c9d1d9'` → `theme.text` (input text)

### 9. `ui/src/components/HITLTable.jsx`

**What**: Import `theme`, replace all hardcoded colors.

**Replacements**:
- `'#f85149'` → `theme.red` (headerText)
- `'#21262d'` → `theme.surfaceInset` (refresh bg)
- `'#30363d'` → `theme.border` (refresh border, th/td borderBottom)
- `'#c9d1d9'` → `theme.text` (refresh text)
- `'#8b949e'` → `theme.textMuted` (empty, th, noPr)
- `'#58a6ff'` → `theme.accent` (link)

### 10. `ui/src/components/ReviewTable.jsx`

**What**: Import `theme`, replace all hardcoded colors in `verdictColors` and `styles` object.

**Replacements in verdictColors**:
- `'#3fb950'` → `theme.green`
- `'#f85149'` → `theme.red`
- `'#d29922'` → `theme.yellow`
- `'#c9d1d9'` → `theme.text` (fallback color)

**Replacements in styles**:
- `'#8b949e'` → `theme.textMuted` (empty, th)
- `'#30363d'` → `theme.border` (th/td borderBottom)

### 11. `ui/src/components/PipelineStatus.jsx`

**What**: Import `theme`, replace all hardcoded colors in STAGES array and `styles` object.

**Replacements in STAGES**:
- `'#a371f7'` → `theme.purple`
- `'#d29922'` → `theme.yellow`
- `'#d18616'` → `theme.orange`

**Replacements in JSX**:
- `'#30363d'` → `theme.border` (inactive connector/border)
- `'#21262d'` → `theme.surfaceInset` (inactive stage bg)
- `'#0d1117'` → `theme.bg` (active stage text)
- `'#484f58'` → `theme.textInactive` (inactive stage text)

**Replacements in styles**:
- `'#0d1117'` → `theme.bg` (container bg)
- `'#30363d'` → `theme.border` (container borderBottom)

---

## Implementation Steps

1. **Define CSS variables in `ui/index.html`**
   - Add `:root { ... }` block inside the existing `<style>` tag, before the `*` reset
   - Include all 19 base colors and 9 alpha variants
   - Update `body` bg/color to use `var(--bg)` and `var(--text)`

2. **Create `ui/src/theme.js`**
   - Export a `theme` object mapping semantic names to `var(--name)` strings
   - Keep it flat (no nesting) for simplicity

3. **Update each component file (9 files)**
   - Add `import { theme } from '../theme'` (or `'./theme'` for App.jsx)
   - Replace every hardcoded hex/rgba value with the corresponding `theme.*` key
   - Work through one file at a time, verifying each replacement against the mapping

4. **Verify the build**
   - Run `make ui` to ensure the Vite build succeeds with no errors
   - Visual spot-check: colors should be IDENTICAL to before (no visible change)

---

## Testing Strategy

Since the React UI has no existing test infrastructure (no test runner in `package.json`, no test files), and these are purely visual-to-identical refactoring changes:

1. **Build verification**: `make ui` must succeed — this catches import errors, syntax issues
2. **Python tests**: `make test` must still pass — ensures no backend breakage
3. **Manual verification**: Run `make run` and visually confirm the dashboard looks identical
4. **Grep audit**: After all changes, run `grep -rn '#[0-9a-fA-F]\{6\}' ui/src/` to confirm zero remaining hardcoded hex colors in JS/JSX files (only `ui/index.html` `:root` block should have them)

No new unit tests needed for this change — it's a mechanical refactoring of string constants with no behavioral change. The build itself serves as the primary validation gate.

---

## Key Considerations

1. **CSS `var()` works in React inline styles**: `style={{ color: 'var(--accent)' }}` is valid and works in all modern browsers. The browser resolves the variable at render time.

2. **No visual change**: This is a pure refactoring. Every hardcoded value maps 1:1 to a CSS variable holding the exact same value. The rendered output must be pixel-identical.

3. **Alpha variants as CSS variables**: Rather than trying to compute alpha from base colors (which requires CSS `color-mix()` or channel decomposition), we define each alpha variant as its own CSS variable. This is simpler and has full browser support.

4. **STAGES arrays in Header and PipelineStatus**: These use `stage.color` dynamically in JSX expressions. The `color` field in the STAGES const will change from a hex string to a `theme.*` reference — this works fine since `var(--purple)` is just a string that the browser resolves.

5. **Groundwork for theming**: Once all colors are CSS variables, adding light mode or alternative themes becomes a matter of overriding `:root` variables (e.g., via `[data-theme="light"] { --bg: #ffffff; ... }`). This is explicitly mentioned as a benefit in the issue.

6. **No `templates/index.html` changes needed**: The legacy file already uses CSS variables correctly. It will NOT be modified.

---
**Summary:** Replace hardcoded hex colors across ui/index.html and 9 React components with CSS custom properties and a shared theme.js constants module.
