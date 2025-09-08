import asyncio
import logging
from typing import Any

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


async def run_agent_process(process_id: str) -> dict[str, Any]:
    """Run an agent process in the background and return status info"""
    if process_id not in AGENT_PROCESSES:
        return {"success": False, "message": f"Unknown agent process: {process_id}"}

    process = AGENT_PROCESSES[process_id]

    try:
        # Create a process to run the command
        process_obj = await asyncio.create_subprocess_shell(
            process["command"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Return immediately with process info
        return {
            "success": True,
            "process_id": process_id,
            "name": process["name"],
            "status": "started",
            "pid": process_obj.pid,
        }
    except Exception as e:
        logger.error(f"Error running agent process {process_id}: {e}")
        return {
            "success": False,
            "process_id": process_id,
            "name": process["name"],
            "error": str(e),
        }


def get_agent_blocks(result: dict[str, Any], user_id: str) -> list:
    """Get rich message blocks for agent process result"""
    if not result.get("success"):
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ Failed to start agent process: {result.get('error', 'Unknown error')}",
                },
            }
        ]

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚀 *Agent Process Started*: {result['name']}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {result['status']}"},
                {"type": "mrkdwn", "text": f"*Process ID:* {result['pid']}"},
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
