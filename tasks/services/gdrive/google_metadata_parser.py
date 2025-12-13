"""
Google Drive Metadata Parser Service

Handles parsing and formatting of Google Drive metadata.
Separated for better maintainability and testability.
"""


class GoogleMetadataParser:
    """Service for parsing and formatting Google Drive metadata"""

    @staticmethod
    def format_permissions(permissions: list[dict]) -> dict:
        """
        Format Google Drive permissions into a structured format.

        Args:
            permissions: Raw permissions from Google Drive API

        Returns:
            Formatted permissions dictionary
        """
        formatted = {
            "readers": [],
            "writers": [],
            "owners": [],
            "is_public": False,
            "anyone_can_read": False,
            "anyone_can_write": False,
        }

        for perm in permissions:
            role = perm.get("role", "reader")
            perm_type = perm.get("type", "user")
            email_address = perm.get("emailAddress", "")
            display_name = perm.get("displayName", email_address)

            # Check for public access
            if perm_type == "anyone":
                formatted["is_public"] = True
                if role in ["reader", "commenter"]:
                    formatted["anyone_can_read"] = True
                elif role in ["writer", "editor"]:
                    formatted["anyone_can_write"] = True
                    formatted["anyone_can_read"] = True  # Writers can also read

            # Categorize by role
            permission_info = {
                "type": perm_type,
                "email": email_address,
                "display_name": display_name,
                "role": role,
            }

            if role == "owner":
                formatted["owners"].append(permission_info)
            elif role in ["writer", "editor"]:
                formatted["writers"].append(permission_info)
            else:  # reader, commenter
                formatted["readers"].append(permission_info)

        return formatted

    @staticmethod
    def get_permissions_summary(permissions: list[dict]) -> str:
        """
        Get deduplicated list of all email addresses who can access the file.

        Args:
            permissions: Raw permissions from Google Drive API

        Returns:
            Comma-separated string of unique email addresses or domain names
        """
        if not permissions:
            return "no_permissions"

        emails = set()  # Use set for automatic deduplication

        for perm in permissions:
            perm_type = perm.get("type", "user")

            if perm_type == "anyone":
                return "anyone"  # If public to the world, just return "anyone"
            elif perm_type == "domain":
                # Whole organization/domain has access
                domain = perm.get("domain", "unknown_domain")
                emails.add(f"domain:{domain}")
            elif perm_type in ["user", "group"]:
                email = perm.get("emailAddress")
                if email:
                    emails.add(email)

        if emails:
            # Sort for consistent ordering
            return ", ".join(sorted(emails))
        else:
            return "no_emails"

    @staticmethod
    def get_owner_emails(owners: list[dict]) -> str:
        """
        Get a simple string of owner emails for metadata.

        Args:
            owners: Raw owners from Google Drive API

        Returns:
            Comma-separated string of owner emails
        """
        if not owners:
            return "unknown"

        emails = []
        for owner in owners:
            email = owner.get("emailAddress", "")
            if email:
                emails.append(email)

        return ", ".join(emails) if emails else "unknown"

    def enrich_file_metadata(self, item: dict, folder_path: str = "") -> dict:
        """
        Enrich a Google Drive file item with comprehensive metadata.

        Args:
            item: Raw file item from Google Drive API
            folder_path: Current folder path for building full paths

        Returns:
            Enriched metadata dictionary
        """
        # Build full path
        current_path = f"{folder_path}/{item['name']}" if folder_path else item["name"]

        # Add comprehensive metadata
        item["full_path"] = current_path
        item["folder_path"] = folder_path

        # Process permissions if available
        # For Shared Drives, use detailed_permissions (from permissions().list() API)
        # For regular drives, use permissions (from files().list() API)
        detailed_perms = item.get("detailed_permissions", [])
        permissions = detailed_perms if detailed_perms else item.get("permissions", [])

        if permissions:
            item["formatted_permissions"] = self.format_permissions(permissions)
            item["permissions_summary"] = self.get_permissions_summary(permissions)

        # Process owners
        import logging

        logger = logging.getLogger(__name__)

        owners = item.get("owners", [])
        logger.info(f"🔍 METADATA PARSER - File: {item.get('name')}")
        logger.info(f"   Initial owners: {owners}")

        if owners:
            owner_emails = self.get_owner_emails(owners)
            item["owner_emails"] = owner_emails
            logger.info(f"   ✅ Set owner_emails from owners field: {owner_emails}")
        else:
            # For Shared Drives, owners field is often empty
            # Try to extract from detailed_permissions instead
            detailed_perms = item.get("detailed_permissions", [])
            logger.info(
                f"   No owners field, checking detailed_permissions: {len(detailed_perms)} entries"
            )
            if detailed_perms:
                # For Shared Drives: look for owner, organizer, or fileOrganizer roles
                # These are the "responsible parties" in Shared Drives
                owner_perms = [
                    p
                    for p in detailed_perms
                    if p.get("role") in ["owner", "organizer", "fileOrganizer"]
                ]
                logger.info(f"   Found {len(owner_perms)} owner/organizer permissions")
                if owner_perms:
                    logger.info(f"   Owner/organizer perms sample: {owner_perms[:2]}")
                    # Convert permission entries to owner format
                    extracted_owners = [
                        {"emailAddress": p.get("emailAddress", "")}
                        for p in owner_perms
                        if p.get("emailAddress")
                    ]
                    if extracted_owners:
                        owner_emails = self.get_owner_emails(extracted_owners)
                        item["owner_emails"] = owner_emails
                        # Store extracted owners for consistency
                        item["owners"] = extracted_owners
                        logger.info(
                            f"   ✅ Set owner_emails from detailed_permissions (Shared Drive): {owner_emails}"
                        )
                    else:
                        logger.warning(
                            "   ⚠️  No email addresses found in owner/organizer permissions"
                        )
                else:
                    logger.warning(
                        "   ⚠️  No owner/organizer role found in detailed_permissions"
                    )
            else:
                logger.warning("   ⚠️  No detailed_permissions available")

        return item

    @staticmethod
    def is_supported_file_type(mime_type: str) -> bool:
        """
        Check if a file type is supported for content extraction.

        Args:
            mime_type: MIME type of the file

        Returns:
            True if file type is supported
        """
        supported_types = [
            # Google Workspace files
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
            # Office documents
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # Text files
            "text/plain",
            "text/markdown",
            "text/csv",
            "application/json",
        ]

        return mime_type in supported_types or mime_type.startswith("text/")
