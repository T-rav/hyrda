# Agent to Slack Output Contract

## Overview

This document defines the standardized output contract between LangGraph agents and the Slack message handler. This contract ensures a clean separation of concerns where **agents own their output formatting** and the **message handler simply displays it**.

## Architecture Principles

### Separation of Concerns

- **Agent Layer**: Responsible for formatting Slack-ready content and defining how attachments should be processed
- **Transport Layer (agent_client)**: Generic pass-through that doesn't inspect or transform data
- **Display Layer (message_handler)**: Follows the contract to display messages and process attachments

### Benefits

✅ **Agent Ownership**: Agents know their data best and format it appropriately for Slack
✅ **Extensibility**: Easy to add new attachment types without changing transport layer
✅ **Simplicity**: No field priority logic, no guessing which field to display
✅ **Reusability**: Any agent can use this contract with zero changes to infrastructure

---

## Contract Specification

### Output Schema

```python
{
    "message": str,              # Required: Slack-ready markdown text
    "attachments": list[dict]    # Optional: Files to process
}
```

### Field Definitions

#### `message` (Required)

**Type**: `str`
**Purpose**: The primary text content to display in Slack
**Format**: Standard markdown (message_handler converts to Slack format)
**Guidelines**:
- Should be concise but complete
- Use standard markdown formatting (not Slack-specific)
- Can include formatting: `**bold**`, `*italic*`, `~~strike~~`, `` `code` ``
- Can include links: `[text](url)`
- Can include emojis: 📊 ✅ 🚀
- Should be self-contained (readable without attachments)
- **No need to worry about Slack formatting quirks** - handler converts automatically

**Example (Standard Markdown)**:
```python
"message": """📊 **Executive Summary**

- Company operates 800+ warehouse locations globally
- Key challenge: Intense competition from Amazon and Walmart
- Opportunity: Cybersecurity consulting and e-commerce modernization

---

💬 *Ask follow-up questions in this thread!*"""
```

**Note**: The message_handler automatically converts this to Slack format:
- `**bold**` → `*bold*` (Slack)
- `*italic*` → `_italic_` (Slack)
- `- list` → `•` (bullets)
- Links, code blocks, etc. are converted appropriately

#### `attachments` (Optional)

**Type**: `list[dict]`
**Purpose**: Additional files or content that can be injected or linked
**Default**: `[]` (empty list if no attachments)

Each attachment is a dictionary with the following fields:

```python
{
    "url": str,           # Required: URL to fetch content from
    "inject": bool,       # Required: Whether to fetch and inject inline
    "type": str,         # Optional: Content type (markdown, pdf, image, etc.)
    "filename": str      # Optional: Display name for the file
}
```

**Attachment Field Details**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | str | ✅ Yes | Full URL to the content (presigned URLs for MinIO/S3) |
| `inject` | bool | ✅ Yes | `true` = fetch and display inline, `false` = just link |
| `type` | str | ❌ No | MIME type or format hint (`markdown`, `pdf`, `image`, etc.) |
| `filename` | str | ❌ No | Human-readable name for logging/debugging |

---

---

## Markdown Conversion

### Agent: Standard Markdown → Handler: Slack Format

Agents should use **standard markdown**. The message_handler automatically converts to Slack's format using `MessageFormatter.format_message()`.

**Conversion Table:**

| Standard Markdown | Slack Format | Example |
|-------------------|--------------|---------|
| `**bold**` | `*bold*` | **Important** → *Important* |
| `*italic*` | `_italic_` | *emphasis* → _emphasis_ |
| `~~strike~~` | `~strike~` | ~~wrong~~ → ~wrong~ |
| `` `code` `` | `` `code` `` | `variable` (unchanged) |
| `[link](url)` | `<url\|link>` | [Google](https://google.com) → <https://google.com\|Google> |
| `- item` | `• item` | Bullets converted |
| `# Heading` | `*Heading*` | Headings → bold |
| `---` | `---` | Horizontal rule (unchanged) |

### Why Standard Markdown?

**Benefits:**
- ✅ **Portability**: Same agent could work with Discord, Teams, etc.
- ✅ **Simplicity**: Agents don't need to know Slack quirks
- ✅ **Maintainability**: One place for Slack-specific logic
- ✅ **Testing**: Test agents with standard markdown parsers

**Example Transformation:**

```markdown
# Company Profile

**Founded**: 2010
*Industry*: Technology

Key findings:
- Revenue: $500M
- Employees: 1,000+

[View Website](https://example.com)
```

**Becomes (Slack):**

```
*Company Profile*

*Founded*: 2010
_Industry_: Technology

Key findings:
• Revenue: $500M
• Employees: 1,000+

<https://example.com|View Website>
```

---

## Processing Flow

```
┌─────────────────┐
│  LangGraph      │
│  Agent Node     │
│  (e.g. profile) │
└────────┬────────┘
         │ Returns standardized output
         │ {message: "standard markdown", attachments}
         ▼
┌─────────────────┐
│  LangGraph      │
│  Output Schema  │
│  Filtering      │
└────────┬────────┘
         │ Validates and passes through
         ▼
┌─────────────────┐
│  agent_client   │
│  (Transport)    │
└────────┬────────┘
         │ Wraps as {type:"result", data:{...}}
         │ Generic pass-through, no inspection
         ▼
┌─────────────────┐
│ message_handler │
│ (Display)       │
└────────┬────────┘
         │
         ├─► 1. Get message field (standard markdown)
         │
         ├─► 2. For each attachment:
         │   ├─► If inject==true: Fetch from URL, replace message with full content
         │   └─► If inject==false: Add link to message
         │
         └─► 3. Convert markdown → Slack format
             └─► MessageFormatter.format_message(final_content)
                 └─► Send to Slack
```

---

## Implementation Examples

### Example 1: Simple Text Response

**Agent returns:**
```python
{
    "message": "✅ Analysis complete! The company has 3 primary competitors.",
    "attachments": []
}
```

**User sees in Slack:**
```
✅ Analysis complete! The company has 3 primary competitors.
```

---

### Example 2: Summary with Full Report (Injected)

**Agent returns:**
```python
{
    "message": """📊 *Executive Summary*

• Key finding 1
• Key finding 2
• Key finding 3

_See full report for details_""",

    "attachments": [
        {
            "url": "http://minio:9000/reports/profile_acme_20231219.md?signature=...",
            "inject": True,
            "type": "markdown",
            "filename": "profile_acme.md"
        }
    ]
}
```

**User sees in Slack:**
```
[Full 50-page markdown report displayed inline]
```

**Why?** `inject: true` tells the handler to fetch the URL and replace the summary with full content.

---

### Example 3: Summary with Link (Not Injected)

**Agent returns:**
```python
{
    "message": """📊 *Summary*

Report generated with 45 pages.

📄 [View Full Report](http://minio:9000/reports/profile_acme.md)""",

    "attachments": [
        {
            "url": "http://minio:9000/reports/profile_acme.md?signature=...",
            "inject": False,
            "type": "markdown",
            "filename": "profile_acme.md"
        }
    ]
}
```

**User sees in Slack:**
```
📊 *Summary*

Report generated with 45 pages.

📄 [View Full Report](http://minio:9000/reports/profile_acme.md)
```

**Why?** `inject: false` means keep the summary, just provide the link.

---

### Example 4: Multiple Attachments

**Agent returns:**
```python
{
    "message": "📊 Analysis complete with 3 supporting files:",
    "attachments": [
        {
            "url": "http://minio:9000/reports/summary.md",
            "inject": True,
            "type": "markdown",
            "filename": "summary.md"
        },
        {
            "url": "http://minio:9000/charts/growth.png",
            "inject": False,
            "type": "image",
            "filename": "growth_chart.png"
        },
        {
            "url": "http://minio:9000/data/financials.csv",
            "inject": False,
            "type": "csv",
            "filename": "financials.csv"
        }
    ]
}
```

**Processing:**
1. First attachment (`inject: true`) → Fetch and replace message with content
2. Second attachment (`inject: false`) → Add link to image
3. Third attachment (`inject: false`) → Add link to CSV

---

## Agent Implementation Guide

### Step 1: Define Output Schema

Add fields to your agent's `OutputState`:

```python
from typing_extensions import TypedDict

class YourAgentOutputState(TypedDict):
    """Output from your agent graph.

    Uses standardized contract for Slack integration:
    - message: Slack-ready markdown text to display
    - attachments: List of URLs with processing instructions
    """

    messages: list[MessageLikeRepresentation]  # LangGraph requirement
    message: str                                # Slack display text
    attachments: list[dict]                     # URLs to process
```

### Step 2: Format Output in Final Node

```python
async def final_node(state: YourState, config: RunnableConfig) -> dict:
    """Generate final output with standardized contract."""

    # Generate your content
    full_report = generate_full_report(state)
    summary = generate_executive_summary(full_report)

    # Upload to storage
    report_url = upload_to_storage(full_report, "report.md")

    # Build standardized output
    attachments = []
    if report_url:
        attachments.append({
            "url": report_url,
            "inject": True,  # Fetch and inject full content
            "type": "markdown",
            "filename": "full_report.md"
        })

    return {
        "message": summary,      # Short summary for display
        "attachments": attachments  # Full report to inject
    }
```

### Step 3: Handle Fallback Cases

```python
# If generation fails, still return valid contract
fallback_message = "⚠️ Unable to generate full report. Partial results available."

return {
    "message": fallback_message,
    "attachments": []  # Empty list is valid
}
```

---

## Message Handler Processing

The message handler in `bot/handlers/message_handlers.py` processes the contract as follows:

```python
# 1. Extract message and attachments
message = data.get("message", "")  # Standard markdown from agent
attachments = data.get("attachments", [])

# 2. Start with the message as display content
final_content = message

# 3. Process each attachment
for attachment in attachments:
    url = attachment.get("url")
    should_inject = attachment.get("inject", False)

    if url and should_inject:
        # Fetch content from URL and replace message
        response = await httpx_client.get(url)
        if response.status_code == 200:
            final_content = response.text  # Replace with full content
        # Fallback to message if fetch fails

# 4. Convert standard markdown → Slack format
formatted = await MessageFormatter.format_message(final_content)
# Converts: **bold** → *bold*, *italic* → _italic_, [links](url) → <url|links>, etc.

# 5. Send to Slack
await slack_service.send_message(formatted)
```

**Key Point**: Step 4 handles ALL markdown conversion, so agents never need to know Slack's format.

---

## Best Practices

### ✅ DO: Use Standard Markdown

```python
# ✅ GOOD: Standard markdown
{
    "message": """**Summary**

Key findings:
- Point 1
- Point 2

Visit [our website](https://example.com)""",
    "attachments": []
}
```

### ❌ DON'T: Use Slack-Specific Format

```python
# ❌ BAD: Slack-specific (unnecessary)
{
    "message": """*Summary*

Key findings:
• Point 1
• Point 2

Visit <https://example.com|our website>""",
    "attachments": []
}
```

### For Injected Content

When `inject: true`, the **fetched content is also converted** from standard markdown to Slack format. So:

```python
# In MinIO file (standard markdown):
# **Important**: This is a heading
# *Note*: Some emphasis
# - Bullet point

# After injection + conversion (Slack):
# *Important*: This is a heading
# _Note_: Some emphasis
# • Bullet point
```

**Recommendation**: Always write standard markdown in uploaded files too.

### Message Composition Tips

1. **Keep summaries short**: 3-5 bullet points max
2. **Use emojis sparingly**: One or two for visual hierarchy
3. **Headings for structure**: Use `##` or `###` for sections
4. **Links are valuable**: Provide context links when relevant
5. **Consider threading**: Long content works better injected vs in message

---

## Testing Your Agent Output

### Unit Test Template

```python
@pytest.mark.asyncio
async def test_agent_output_contract():
    """Test that agent returns valid contract."""

    # Run agent
    result = await your_agent.ainvoke({"query": "test"})

    # Verify contract
    assert "message" in result, "Must include 'message' field"
    assert isinstance(result["message"], str), "Message must be string"
    assert len(result["message"]) > 0, "Message must not be empty"

    # Verify attachments (if present)
    if "attachments" in result:
        assert isinstance(result["attachments"], list), "Attachments must be list"
        for attachment in result["attachments"]:
            assert "url" in attachment, "Each attachment must have 'url'"
            assert "inject" in attachment, "Each attachment must have 'inject'"
            assert isinstance(attachment["inject"], bool), "inject must be bool"
```

### Integration Test Template

```python
@pytest.mark.asyncio
async def test_slack_integration():
    """Test that message handler correctly processes contract."""

    # Mock agent output
    agent_output = {
        "message": "Test summary",
        "attachments": [
            {
                "url": "http://test.com/report.md",
                "inject": True,
                "type": "markdown",
                "filename": "test.md"
            }
        ]
    }

    # Mock HTTP fetch
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "Full content"

        # Process through message handler
        # ... verify final_content == "Full content"
```

---

## Troubleshooting

### Issue: Message not displaying

**Check:**
- Is `message` field present in output?
- Is `message` a non-empty string?
- Is output schema (`OutputState`) correctly defined?

### Issue: Attachment not injecting

**Check:**
- Is `inject` set to `true` (boolean, not string)?
- Is URL accessible from the bot container?
- Are presigned URLs still valid (not expired)?
- Check logs for HTTP fetch errors

### Issue: Content too large for Slack

**Solution:**
- Slack has a message size limit (~40,000 characters)
- For large content, use `inject: false` and provide a link
- Or split into multiple messages

---

## Future Extensions

This contract is designed to be extensible. Future enhancements could include:

### Additional Attachment Types

```python
{
    "url": "http://...",
    "inject": True,
    "type": "image",
    "display": "inline"  # vs "thumbnail"
}
```

### Caching Hints

```python
{
    "message": "...",
    "attachments": [...],
    "cache_key": "profile_acme_v2",  # For follow-up questions
    "ttl": 3600  # Cache lifetime in seconds
}
```

### Interactive Elements

```python
{
    "message": "...",
    "attachments": [...],
    "actions": [
        {"label": "Regenerate", "action": "regenerate"},
        {"label": "Export PDF", "action": "export_pdf"}
    ]
}
```

---

## Summary

**Key Takeaways:**

1. ✅ **Use standard markdown** - not Slack-specific format
2. ✅ **Always return** `message` field with standard markdown
3. ✅ **Optionally return** `attachments` list with `url` and `inject` fields
4. ✅ **Handler converts** standard markdown → Slack format automatically
5. ✅ **Use `inject: true`** when you want full content displayed inline
6. ✅ **Use `inject: false`** when you want to provide a link only

**Contract in one line:**
> Agents return `{message: "standard markdown", attachments: [{url, inject}]}` and the message handler converts to Slack format and displays it.

---

## Questions?

For implementation questions or contract modifications, see:
- Implementation: `bot/handlers/message_handlers.py` (lines 380-420)
- Example: `external_agents/profile/nodes/final_report.py` (lines 354-370)
- Tests: `bot/tests/test_message_handlers_unit.py`
