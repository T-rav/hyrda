"""Integration tests for GoalBotSchedulerJob.

These tests verify the exact HTTP request/response contracts without requiring
running services: URL construction, headers, request bodies, and response handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from jobs.goal_bot_scheduler import GoalBotSchedulerJob

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(json_body=None, status_code=200):
    """Build a minimal httpx.Response with a JSON body.

    Attaches a dummy request so that raise_for_status() works correctly.
    """
    import json

    content = json.dumps(json_body or {}).encode()
    response = httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": "application/json"},
    )
    # httpx.Response.raise_for_status() requires _request to be set
    response.request = httpx.Request("GET", "http://test-placeholder/")
    return response


@pytest.fixture
def settings():
    return MagicMock()


@pytest.fixture
def job(settings):
    with patch.dict(
        "os.environ",
        {
            "CONTROL_PLANE_URL": "http://control-plane:6001",
            "AGENT_SERVICE_URL": "http://agent-service:8000",
            "SERVICE_API_KEY": "integration-test-key",
        },
    ):
        return GoalBotSchedulerJob(settings)


@pytest.fixture
def job_no_api_key(settings):
    with patch.dict(
        "os.environ",
        {
            "CONTROL_PLANE_URL": "http://control-plane:6001",
            "AGENT_SERVICE_URL": "http://agent-service:8000",
            "SERVICE_API_KEY": "",
        },
    ):
        return GoalBotSchedulerJob(settings)


# ---------------------------------------------------------------------------
# Contract: GET /api/goal-bots/due
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_due_bots_request_url_and_auth_header(job):
    """Exact URL and X-Service-API-Key header sent to control-plane."""
    captured = []

    async def capturing_get(url, **kwargs):
        captured.append({"url": url, "headers": kwargs.get("headers", {})})
        return _make_response({"due_bots": [], "count": 0})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(side_effect=capturing_get)
        await job._execute_job()

    assert len(captured) == 1
    assert captured[0]["url"] == "http://control-plane:6001/api/goal-bots/due"
    assert captured[0]["headers"].get("X-Service-API-Key") == "integration-test-key"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_due_bots_omits_auth_header_when_no_key(job_no_api_key):
    """When SERVICE_API_KEY is empty, X-Service-API-Key header must not be sent."""
    captured_headers = []

    async def capturing_get(url, **kwargs):
        captured_headers.append(kwargs.get("headers", {}))
        return _make_response({"due_bots": [], "count": 0})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(side_effect=capturing_get)
        await job_no_api_key._execute_job()

    assert len(captured_headers) == 1
    assert "X-Service-API-Key" not in captured_headers[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_response_schema_reads_due_bots_key(job):
    """Job reads 'due_bots' key (not 'bots' or 'data') from the response."""
    # Correct key: due_bots — job finds 1 bot
    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(
            return_value=_make_response(
                {"due_bots": [{"bot_id": "b1", "name": "Bot1"}]}
            )
        )
        inst.post = AsyncMock(
            return_value=_make_response({"success": False, "error": "already running"})
        )
        result = await job._execute_job()

    assert result["due_bots_found"] == 1

    # Wrong key: bots — job should see zero
    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"bots": [{"bot_id": "b1"}]}))
        result = await job._execute_job()

    assert result["due_bots_found"] == 0


# ---------------------------------------------------------------------------
# Contract: POST /api/goal-bots/runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_run_request_url_and_body(job):
    """POST /api/goal-bots/runs sends {'bot_id': <id>} with auth header."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot", "agent_name": "research"}
    captured_posts = []

    async def capturing_post(url, **kwargs):
        captured_posts.append(
            {
                "url": url,
                "json": kwargs.get("json"),
                "headers": kwargs.get("headers", {}),
            }
        )
        if "execute" in url:
            return _make_response({}, status_code=200)
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-xyz"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(side_effect=capturing_post)
        await job._execute_job()

    create_run = next(
        (
            p
            for p in captured_posts
            if "goal-bots/runs" in p["url"]
            and "start" not in p["url"]
            and "execute" not in p["url"]
        ),
        None,
    )
    assert create_run is not None
    assert create_run["url"] == "http://control-plane:6001/api/goal-bots/runs"
    assert create_run["json"] == {"bot_id": "bot-abc"}
    assert create_run["headers"].get("X-Service-API-Key") == "integration-test-key"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_run_success_increments_runs_created(job):
    """success=True with run.run_id increments runs_created and runs_started."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot"}

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(
            side_effect=[
                _make_response({"success": True, "run": {"run_id": "run-xyz"}}),
                _make_response({}),
                _make_response({}, status_code=200),
            ]
        )
        result = await job._execute_job()

    assert result["runs_created"] == 1
    assert result["runs_started"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_run_skipped_when_success_false(job):
    """success=False means run must not be started; only one POST is made."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot"}

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(
            return_value=_make_response(
                {"success": False, "error": "Bot already has a running job"}
            )
        )
        result = await job._execute_job()

    assert result["runs_created"] == 0
    assert result["runs_started"] == 0
    inst.post.assert_called_once()


# ---------------------------------------------------------------------------
# Contract: POST /api/goal-bots/runs/{run_id}/start
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_start_run_uses_run_id_from_create_run_response(job):
    """Start URL must embed the run_id returned by the create-run response."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot"}
    captured_urls = []

    async def capturing_post(url, **kwargs):
        captured_urls.append(url)
        if "execute" in url:
            return _make_response({}, status_code=200)
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-xyz-123"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(side_effect=capturing_post)
        await job._execute_job()

    start_url = next((u for u in captured_urls if "start" in u), None)
    assert start_url == "http://control-plane:6001/api/goal-bots/runs/run-xyz-123/start"


# ---------------------------------------------------------------------------
# Contract: POST {agent_service_url}/api/goal-bots/{bot_id}/execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_execute_url_and_body(job):
    """Agent-service POST uses correct URL and includes run_id + bot in body."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot", "agent_name": "research"}
    captured_posts = []

    async def capturing_post(url, **kwargs):
        captured_posts.append({"url": url, "json": kwargs.get("json")})
        if "execute" in url:
            return _make_response({}, status_code=200)
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-xyz-123"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(side_effect=capturing_post)
        await job._execute_job()

    agent_post = next((p for p in captured_posts if "agent-service" in p["url"]), None)
    assert agent_post is not None, "POST to agent-service not found"
    assert (
        agent_post["url"] == "http://agent-service:8000/api/goal-bots/bot-abc/execute"
    )
    assert agent_post["json"]["run_id"] == "run-xyz-123"
    assert agent_post["json"]["bot"] == due_bot


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_timeout_treated_as_success(job):
    """TimeoutException from agent-service is fire-and-forget — counts as success."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot"}

    async def post_side_effect(url, **kwargs):
        if "execute" in url:
            raise httpx.TimeoutException("timed out")
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-xyz"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(side_effect=post_side_effect)
        result = await job._execute_job()

    assert result["runs_started"] == 1
    assert result["records_success"] == 1
    assert result["records_failed"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_http_400_counts_as_failure(job):
    """HTTP 4xx from agent-service counts as records_failed."""
    due_bot = {"bot_id": "bot-abc", "name": "Alpha Bot"}

    async def post_side_effect(url, **kwargs):
        if "execute" in url:
            return _make_response({}, status_code=400)
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-xyz"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": [due_bot]}))
        inst.post = AsyncMock(side_effect=post_side_effect)
        result = await job._execute_job()

    assert result["records_failed"] == 1
    assert result["records_success"] == 0


# ---------------------------------------------------------------------------
# Multi-bot processing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_due_bots_all_processed(job):
    """All due bots must be processed independently."""
    due_bots = [
        {"bot_id": "bot-1", "name": "Bot One"},
        {"bot_id": "bot-2", "name": "Bot Two"},
        {"bot_id": "bot-3", "name": "Bot Three"},
    ]
    post_responses = []
    for bot in due_bots:
        post_responses.append(
            _make_response({"success": True, "run": {"run_id": f"run-{bot['bot_id']}"}})
        )
        post_responses.append(_make_response({}, status_code=200))  # start
        post_responses.append(_make_response({}, status_code=200))  # execute

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": due_bots}))
        inst.post = AsyncMock(side_effect=post_responses)
        result = await job._execute_job()

    assert result["due_bots_found"] == 3
    assert result["runs_created"] == 3
    assert result["runs_started"] == 3
    assert result["records_success"] == 3
    assert result["records_failed"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_one_bot_failing_does_not_stop_others(job):
    """If one bot's create-run returns success=False, the others are still processed."""
    due_bots = [
        {"bot_id": "bot-fail", "name": "Failing Bot"},
        {"bot_id": "bot-ok", "name": "OK Bot"},
    ]

    async def post_side_effect(url, **kwargs):
        json_body = kwargs.get("json", {})
        if json_body.get("bot_id") == "bot-fail":
            return _make_response({"success": False, "error": "already running"})
        if "execute" in url:
            return _make_response({}, status_code=200)
        if "start" in url:
            return _make_response({}, status_code=200)
        return _make_response({"success": True, "run": {"run_id": "run-ok"}})

    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(return_value=_make_response({"due_bots": due_bots}))
        inst.post = AsyncMock(side_effect=post_side_effect)
        result = await job._execute_job()

    assert result["due_bots_found"] == 2
    assert result["runs_created"] == 1
    assert result["runs_started"] == 1
    assert result["records_success"] == 1


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_connection_error_returns_early(job):
    """HTTPError from the initial GET stops execution and records the error."""
    with patch("httpx.AsyncClient") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value.__aenter__.return_value = inst
        inst.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        result = await job._execute_job()

    assert result["due_bots_found"] == 0
    assert result["runs_created"] == 0
    assert len(result["errors"]) >= 1
    assert any("Connection refused" in e for e in result["errors"])
