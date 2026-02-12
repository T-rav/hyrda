"""HubSpot credential management endpoints."""

import json
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hubspot")


class HubSpotCredentialRequest(BaseModel):
    """Request body for creating HubSpot credentials."""

    credential_name: str
    access_token: str
    client_secret: str


@router.post("/credentials")
async def create_hubspot_credential(request: HubSpotCredentialRequest):
    """
    Store HubSpot credentials (access token + client secret) encrypted in database.
    """
    # Validate credential_name
    if len(request.credential_name) > 255:
        raise HTTPException(
            status_code=400, detail="credential_name must be 255 characters or less"
        )

    if not re.match(r"^[a-zA-Z0-9 _\-\.]+$", request.credential_name):
        raise HTTPException(
            status_code=400,
            detail="credential_name contains invalid characters",
        )

    # Generate credential ID
    credential_id = str(uuid.uuid4())

    # Create token data to encrypt
    token_data = {
        "access_token": request.access_token,
        "client_secret": request.client_secret,
    }

    # Encrypt the token data
    encryption_service = get_encryption_service()
    encrypted_token = encryption_service.encrypt(json.dumps(token_data))

    # Store in database
    credential = OAuthCredential(
        credential_id=credential_id,
        credential_name=request.credential_name,
        provider="hubspot",
        encrypted_token=encrypted_token,
        token_metadata={"provider": "hubspot"},
    )

    try:
        with get_db_session() as session:
            session.add(credential)
            session.commit()

        logger.info(
            f"Created HubSpot credential: {request.credential_name} ({credential_id})"
        )

        return {
            "credential_id": credential_id,
            "credential_name": request.credential_name,
            "provider": "hubspot",
            "message": "HubSpot credentials stored successfully",
        }

    except Exception as e:
        logger.error(f"Failed to store HubSpot credentials: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to store credentials: {e}"
        ) from e


@router.get("/credentials")
async def list_hubspot_credentials():
    """List all HubSpot credentials (without exposing tokens)."""
    try:
        with get_db_session() as session:
            credentials = (
                session.query(OAuthCredential)
                .filter(OAuthCredential.provider == "hubspot")
                .all()
            )

            return [cred.to_dict() for cred in credentials]

    except Exception as e:
        logger.error(f"Failed to list HubSpot credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/credentials/{credential_id}")
async def delete_hubspot_credential(credential_id: str):
    """Delete a HubSpot credential."""
    try:
        with get_db_session() as session:
            credential = (
                session.query(OAuthCredential)
                .filter(
                    OAuthCredential.credential_id == credential_id,
                    OAuthCredential.provider == "hubspot",
                )
                .first()
            )

            if not credential:
                raise HTTPException(status_code=404, detail="Credential not found")

            session.delete(credential)
            session.commit()

            logger.info(f"Deleted HubSpot credential: {credential_id}")
            return {"message": "Credential deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot credential: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
