# ADR-0018: Screenshot Capture Pipeline Architecture

**Status:** Accepted
**Date:** 2026-03-01

## Context

HydraFlow's dashboard includes a "Report Issue" feature that captures a
screenshot of the current dashboard state, allows the user to annotate it, and
submits it as a GitHub issue with the image attached via a GitHub Gist. Because
the dashboard displays pipeline data, agent transcripts, and event logs, the
screenshot payload can inadvertently contain secrets (API keys, tokens, or
sensitive configuration values rendered in the UI).

The pipeline must balance screenshot fidelity (useful for debugging) against
security (no secret leakage in uploaded images). It must also handle
html2canvas rendering failures caused by unsupported CSS (e.g. CSS Color Level 4
`color()` functions) that vary across browser environments.

## Decision

Adopt a **defense-in-depth screenshot pipeline** with three distinct security
layers and a progressive-fallback capture strategy:

### 1. Frontend DOM redaction (always active)

Before html2canvas renders the cloned DOM, `redactSensitiveElements()` replaces
all elements matching `[data-sensitive]` with an opaque placeholder
(`"[Content redacted for security]"`). This is the **primary protection** — it
prevents sensitive content from entering the captured image at all.

Components that display unfiltered system data (e.g. `EventLog`, `TranscriptPreview`)
are marked with `data-sensitive="true"`. New components that render user-supplied
or agent-generated content must also carry this attribute.

### 2. Three-attempt progressive fallback capture

`captureDashboardScreenshot()` in `Header.jsx` tries three html2canvas
configurations in order:

1. **Full fidelity** — captures computed styles, native `devicePixelRatio`,
   cross-origin image filtering. Produces the highest-quality screenshot.
2. **Safe mode** — drops computed style cloning, uses fixed `scale: 1`. Avoids
   failures from complex CSS that html2canvas cannot parse.
3. **Aggressive sanitization** — enables `foreignObjectRendering`, strips all
   `<style>`/`<link>` elements, and forces baseline colors on every DOM element.
   Replaces any CSS `color()` function values with fallback hex colors. This
   is the last resort when the browser's CSS is entirely incompatible with
   html2canvas.

All three attempts invoke `redactSensitiveElements()` via the `onclone`
callback, ensuring redaction is never bypassed regardless of which attempt
succeeds.

### 3. Backend temp-file staging + native GitHub upload

After dequeuing a report, `ReportIssueLoop` asks `PRManager.save_screenshot_to_temp()`
to decode the base64 PNG and write it to a temporary file (e.g.,
`/tmp/hydraflow-screenshot-XXXX.png`). The Markdown body handed to the reporting
agent already includes `![Screenshot](<absolute-path>)`. When the agent runs
`gh issue create --body-file`, the GitHub CLI detects the local reference,
uploads the image to GitHub's CDN, rewrites the Markdown to point at the hosted
URL, and the temp file is cleaned up at the end of the loop. No gists or
secondary storage locations are involved.

## Consequences

**Positive:**
- Defense-in-depth: frontend DOM redaction remains the first line, and the
  backend writes screenshots directly to disk before GitHub uploads them — no
  intermediate services to secure.
- Progressive fallback ensures screenshots succeed across browser environments
  with varying CSS support, avoiding blank or broken captures.
- The `data-sensitive` attribute convention is simple to adopt — new components
  only need a single attribute to opt in to redaction.
- Native GitHub attachments keep artifacts under the same retention and access
  controls as the resulting bug report.

**Trade-offs:**
- Three capture attempts add latency to the screenshot flow (each failed attempt
  is caught and retried). In practice, the first attempt usually succeeds.
- The aggressive sanitization fallback (attempt 3) produces lower-fidelity
  screenshots with stripped styles. This is acceptable as a last resort but
  means some bug reports may have less visual context.
- Because GitHub rewrites the Markdown after upload, the backend must defer
  temp-file cleanup until the CLI finishes successfully.

## Alternatives considered

1. **Server-side rendering (Puppeteer/Playwright).**
   Rejected: adds a headless browser dependency to the backend, increases
   resource requirements, and introduces latency. Client-side html2canvas is
   sufficient for dashboard-state screenshots and avoids the operational burden.

2. **Pixel-level OCR scanning on the backend.**
   Rejected: OCR adds significant processing time and a heavy dependency
   (Tesseract or similar). The zlib-compressed base64 scan is lightweight, and
   the primary defense (DOM redaction) operates before capture.

3. **External artifact store (S3, GCS, etc.)**
   Rejected: introduces credential management, lifecycle policies, and redundant
   infrastructure when GitHub already hosts issue attachments securely.

4. **Single html2canvas configuration with no fallback.**
   Rejected: html2canvas frequently fails on modern CSS features (especially
   `color()` function syntax). A single configuration would leave users with
   broken screenshot functionality on affected browsers.

## Related

- **Supersedes ADR-0013** — ADR-0013 documented the original screenshot pipeline
  with hardcoded `--public` gists and no DOM redaction. This ADR adds defense-in-depth
  security (DOM redaction plus native GitHub uploads), making ADR-0013's public-gist-only
  design obsolete.
- Source memory: #1734
- ADR issue: #1749
- `src/ui/src/components/Header.jsx` — `captureDashboardScreenshot()`, `redactSensitiveElements()`
- `src/ui/src/components/ReportIssueModal.jsx` — annotation canvas and submission
- `src/ui/src/constants.js` — `SENSITIVE_SELECTORS`
- `src/report_issue_loop.py` — `ReportIssueLoop._do_work()`
- `src/pr_manager.py` — `PRManager.save_screenshot_to_temp()`
