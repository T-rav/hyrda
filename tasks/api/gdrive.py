"""Google Drive OAuth and integration endpoints.

Note: This is a simplified version. Full OAuth flow logic remains in original app.py
for now and can be extracted in a future refactor.
"""

import logging

from flask import Blueprint, Response, jsonify

logger = logging.getLogger(__name__)

# Create blueprint
gdrive_bp = Blueprint("gdrive", __name__, url_prefix="/api/gdrive")


# OAuth endpoints will be added in future refactor
# For now, keeping complex OAuth flow in main app.py
