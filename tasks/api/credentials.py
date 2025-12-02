"""OAuth credential management endpoints."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies.auth import get_current_user

from models.base import get_db_session
from models.oauth_credential import OAuthCredential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/credentials")


@router.get("")
async def list_credentials(request: Request, user: dict = Depends(get_current_user)):
    """List all stored Google OAuth credentials with status.

    Returns:
        Dictionary with list of credentials and their status
    """
    try:
        with get_db_session() as db_session:
            credentials = db_session.query(OAuthCredential).all()
            creds_with_status = []

            for cred in credentials:
                cred_dict = cred.to_dict()

                # Check token expiry status
                expiry_str = (
                    cred.token_metadata.get("expiry") if cred.token_metadata else None
                )
                if expiry_str:
                    try:
                        # Parse ISO format expiry timestamp
                        expiry = datetime.fromisoformat(
                            expiry_str.replace("Z", "+00:00")
                        )
                        now = datetime.now(UTC)

                        if expiry <= now:
                            cred_dict["status"] = "expired"
                            cred_dict["status_message"] = (
                                "Token expired - refresh required"
                            )
                        elif (
                            expiry - now
                        ).total_seconds() < 86400:  # Less than 24 hours
                            cred_dict["status"] = "expiring_soon"
                            cred_dict["status_message"] = "Token expires soon"
                        else:
                            cred_dict["status"] = "active"
                            cred_dict["status_message"] = "Active"

                        cred_dict["expires_at"] = expiry_str
                    except Exception as e:
                        logger.warning(
                            f"Error parsing token expiry for {cred.credential_id}: {e}"
                        )
                        cred_dict["status"] = "unknown"
                        cred_dict["status_message"] = "Status unknown"
                else:
                    cred_dict["status"] = "unknown"
                    cred_dict["status_message"] = "No expiry info"

                creds_with_status.append(cred_dict)

            return {"credentials": creds_with_status}

    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{cred_id}")
async def delete_credential(
    request: Request, cred_id: str, user: dict = Depends(get_current_user)
):
    """Delete a stored Google OAuth credential.

    Args:
        cred_id: Credential identifier

    Returns:
        Success message
    """
    try:
        with get_db_session() as db_session:
            credential = (
                db_session.query(OAuthCredential)
                .filter(OAuthCredential.credential_id == cred_id)
                .first()
            )

            if not credential:
                raise HTTPException(status_code=404, detail="Credential not found")

            db_session.delete(credential)
            db_session.commit()

            logger.info(f"Deleted credential: {credential.credential_name} ({cred_id})")

            return {"message": "Credential deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credential: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
