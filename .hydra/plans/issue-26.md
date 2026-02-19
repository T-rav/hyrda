# Plan for Issue #26

## Issue Restatement

The `<input>` field at `templates/index.html:333` has a visual label (`<span id="human-input-question">`) that is not programmatically associated with the input. Screen readers cannot determine what the input is for. The fix is to add `aria-labelledby="human-input-question"` to the input element.

## Files to Modify

### 1. `templates/index.html` (line 333)

**Change:** Add `aria-labelledby="human-input-question"` attribute to the input element.

Before:
```html
<input type="text" id="human-input-field" placeholder="Type your response..." />
```

After:
```html
<input type="text" id="human-input-field" aria-labelledby="human-input-question" placeholder="Type your response..." />
```

This is the only change needed. The existing `<span id="human-input-question">` already has the correct `id`, so `aria-labelledby` will link them semantically.

**Why `aria-labelledby` over `<label for>`:** The `<span>` text is dynamically updated via JavaScript (`templates/index.html:398`), and the banner uses flexbox layout with specific styling. Using `aria-labelledby` is the least invasive approach — it requires no structural HTML changes, no CSS adjustments, and works correctly with the dynamic text updates.

## Implementation Steps

1. Open `templates/index.html`.
2. On line 333, add `aria-labelledby="human-input-question"` to the `<input>` tag.
3. Write a test verifying the attribute is present (see below).
4. Run `make quality` to validate.

## Testing Strategy

### New test in `tests/test_dashboard.py`

Add a test that verifies the rendered HTML contains the `aria-labelledby` attribute on the input field. The dashboard already serves this template via FastAPI's `Jinja2Templates`, so the existing test client can fetch the HTML.

**Test:**
```python
class TestAccessibility:
    """Tests for accessibility attributes in the dashboard HTML."""

    def test_human_input_field_has_aria_labelledby(self, client):
        """The human-input field must be linked to its label for screen readers."""
        response = client.get("/")
        html = response.text
        assert 'aria-labelledby="human-input-question"' in html
```

This test ensures the attribute is not accidentally removed in future changes.

## Key Considerations

- **No visual change** — This is purely a semantic/accessibility fix; nothing changes visually.
- **Dynamic label text** — The span's text content is updated dynamically via JS (`document.getElementById('human-input-question').textContent = ...`). `aria-labelledby` reads the current text content of the referenced element, so it works correctly with dynamic updates.
- **React UI** — The React frontend (`ui/src/`) does not contain a matching human-input component, so no changes are needed there.
- **Backward compatibility** — Adding an ARIA attribute is purely additive; no existing behavior is affected.

---
**Summary:** Add `aria-labelledby="human-input-question"` to the human-input text field in `templates/index.html` and add a regression test.
