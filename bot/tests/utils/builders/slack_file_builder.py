"""
SlackFileBuilder for test utilities
"""

from typing import Any


class SlackFileBuilder:
    """Builder for creating Slack file objects"""

    def __init__(self):
        self._id = "F12345"
        self._name = "test.txt"
        self._mimetype = "text/plain"
        self._size = 1024
        self._url_private = "https://files.slack.com/test"
        self._content = None

    def with_id(self, file_id: str):
        """Set file ID"""
        self._id = file_id
        return self

    def with_name(self, name: str):
        """Set filename"""
        self._name = name
        return self

    def with_mimetype(self, mimetype: str):
        """Set MIME type"""
        self._mimetype = mimetype
        return self

    def as_pdf(self):
        """Configure as PDF file"""
        self._mimetype = "application/pdf"
        if not self._name.endswith(".pdf"):
            self._name = f"{self._name.rsplit('.', 1)[0]}.pdf"
        return self

    def as_text(self):
        """Configure as text file"""
        self._mimetype = "text/plain"
        if not self._name.endswith(".txt"):
            self._name = f"{self._name.rsplit('.', 1)[0]}.txt"
        return self

    def as_image(self):
        """Configure as image file"""
        self._mimetype = "image/png"
        if not self._name.endswith((".png", ".jpg", ".jpeg")):
            self._name = f"{self._name.rsplit('.', 1)[0]}.png"
        return self

    def with_size(self, size: int):
        """Set file size"""
        self._size = size
        return self

    def with_url(self, url: str):
        """Set file URL"""
        self._url_private = url
        return self

    def with_content(self, content: bytes):
        """Set file content"""
        self._content = content
        self._size = len(content)
        return self

    def build(self) -> dict[str, Any]:
        """Build the Slack file object"""
        file_obj = {
            "id": self._id,
            "name": self._name,
            "mimetype": self._mimetype,
            "size": self._size,
            "url_private": self._url_private,
        }
        if self._content:
            file_obj["content"] = self._content
        return file_obj
