import asyncio
import logging

from models import ApiResponse

logger = logging.getLogger(__name__)

# Available agent processes
# Note: These are example processes. Replace with your actual processing scripts.
AGENT_PROCESSES = {
    "agent_example_process": {
        "name": "Example Process",
        "description": "An example agent process (replace with your actual processes)",
        "command": "echo 'Example process executed successfully'",
    }
    # Add your actual agent processes here:
    # "agent_your_process": {
    #     "name": "Your Process Name",
    #     "description": "What your process does",
    #     "command": "python /path/to/your/script.py"
    # }
}


async def run_agent_process(process_id: str) -> ApiResponse:
    """Run an agent process in the background and return status info"""
    if process_id not in AGENT_PROCESSES:
        return ApiResponse(
            success=False, error_message=f"Unknown agent process: {process_id}"
        )

    process = AGENT_PROCESSES[process_id]

    try:
        # Create a process to run the command
        process_obj = await asyncio.create_subprocess_shell(
            process["command"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Return immediately with process info
        return ApiResponse(
            success=True,
            data={
                "process_id": process_id,
                "name": process["name"],
                "status": "started",
                "pid": process_obj.pid,
            },
        )
    except Exception as e:
        logger.error(f"Error running agent process {process_id}: {e}")
        return ApiResponse(
            success=False,
            data={
                "process_id": process_id,
                "name": process["name"],
            },
            error_message=str(e),
        )


def get_agent_blocks(result: ApiResponse, user_id: str) -> list:
    """Get rich message blocks for agent process result"""
    if not result.success:
        error_msg = result.error_message or "Unknown error"
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ Failed to start agent process: {error_msg}",
                },
            }
        ]

    # Extract data from the response
    data = result.data or {}
    name = data.get("name", "Unknown Process")
    status = data.get("status", "unknown")
    pid = data.get("pid", "unknown")

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚀 *Agent Process Started*: {name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {status}"},
                {"type": "mrkdwn", "text": f"*Process ID:* {pid}"},
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Process started by <@{user_id}>"}
            ],
        },
    ]


def get_available_processes() -> dict[str, dict[str, str]]:
    """Get all available agent processes"""
    return AGENT_PROCESSES
