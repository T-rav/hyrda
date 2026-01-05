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
        Get a simple string summary of Google Drive permissions for metadata.

        Args:
            permissions: Raw permissions from Google Drive API

        Returns:
            Simple string summary of permissions
        """
        if not permissions:
            return "no_permissions"

        summary_parts = []
        anyone_access = False
        user_count = 0

        for perm in permissions:
            role = perm.get("role", "reader")
            perm_type = perm.get("type", "user")

            if perm_type == "anyone":
                anyone_access = True
                summary_parts.append(f"anyone_{role}")
            elif perm_type in ["user", "group"]:
                user_count += 1

        if anyone_access and user_count > 0:
            return f"public_plus_{user_count}_users"
        elif anyone_access:
            return "public_access"
        elif user_count > 0:
            return f"private_{user_count}_users"
        else:
            return "restricted"

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
        permissions = item.get("permissions", [])
        if permissions:
            item["formatted_permissions"] = self.format_permissions(permissions)
            item["permissions_summary"] = self.get_permissions_summary(permissions)

        # Process owners
        owners = item.get("owners", [])
        if owners:
            item["owner_emails"] = self.get_owner_emails(owners)

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
