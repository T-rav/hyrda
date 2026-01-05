"""Tests for update_env.py environment variable replacement script."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from update_env import read_env_file, update_env_file_with_local_env, write_env_file


class TestReadEnvFile:
    """Test read_env_file function."""

    def test_reads_file_successfully(self, tmp_path: Path) -> None:
        """Test that read_env_file reads a file and returns lines."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        # Act
        lines = read_env_file(str(env_file))

        # Assert
        assert len(lines) == 2
        assert lines[0] == "KEY1=value1\n"
        assert lines[1] == "KEY2=value2\n"

    def test_reads_empty_file(self, tmp_path: Path) -> None:
        """Test reading an empty file."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text("")

        # Act
        lines = read_env_file(str(env_file))

        # Assert
        assert lines == []

    def test_raises_error_on_missing_file(self, tmp_path: Path) -> None:
        """Test that reading a non-existent file raises an error."""
        # Arrange
        non_existent = tmp_path / "missing.env"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            read_env_file(str(non_existent))


class TestWriteEnvFile:
    """Test write_env_file function."""

    def test_writes_lines_to_file(self, tmp_path: Path) -> None:
        """Test that write_env_file writes lines to a file."""
        # Arrange
        env_file = tmp_path / ".env"
        lines = ["KEY1=value1\n", "KEY2=value2\n"]

        # Act
        write_env_file(str(env_file), lines)

        # Assert
        content = env_file.read_text()
        assert content == "KEY1=value1\nKEY2=value2\n"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that write_env_file overwrites existing content."""
        # Arrange
        env_file = tmp_path / ".env"
        env_file.write_text("OLD_CONTENT=old\n")
        lines = ["NEW_CONTENT=new\n"]

        # Act
        write_env_file(str(env_file), lines)

        # Assert
        content = env_file.read_text()
        assert content == "NEW_CONTENT=new\n"
        assert "OLD_CONTENT" not in content


class TestUpdateEnvFileWithLocalEnv:
    """Test update_env_file_with_local_env function."""

    def test_replaces_get_from_local_env_with_actual_values(self, tmp_path: Path) -> None:
        """Test that GET_FROM_LOCAL_ENV is replaced with environment variable values."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text("API_KEY=GET_FROM_LOCAL_ENV\nHOST=localhost\n")

        # Act
        with patch.dict(os.environ, {"API_KEY": "secret-key-123"}):
            update_env_file_with_local_env(str(input_file), str(output_file))

        # Assert
        content = output_file.read_text()
        assert "API_KEY=secret-key-123\n" in content
        assert "HOST=localhost\n" in content
        assert "GET_FROM_LOCAL_ENV" not in content

    def test_exits_on_missing_environment_variable(self, tmp_path: Path) -> None:
        """Test that script exits with error if required env var is missing."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text("MISSING_VAR=GET_FROM_LOCAL_ENV\n")

        # Act & Assert
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                update_env_file_with_local_env(str(input_file), str(output_file))
            assert exc_info.value.code == 1

    def test_preserves_non_get_from_local_env_lines(self, tmp_path: Path) -> None:
        """Test that lines not using GET_FROM_LOCAL_ENV are preserved unchanged."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text(
            "# Comment line\n"
            "STATIC_VAR=static_value\n"
            "DYNAMIC_VAR=GET_FROM_LOCAL_ENV\n"
            "ANOTHER_STATIC=another_value\n"
        )

        # Act
        with patch.dict(os.environ, {"DYNAMIC_VAR": "replaced_value"}):
            update_env_file_with_local_env(str(input_file), str(output_file))

        # Assert
        content = output_file.read_text()
        assert "# Comment line\n" in content
        assert "STATIC_VAR=static_value\n" in content
        assert "DYNAMIC_VAR=replaced_value\n" in content
        assert "ANOTHER_STATIC=another_value\n" in content

    def test_handles_multiple_replacements(self, tmp_path: Path) -> None:
        """Test replacing multiple environment variables."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text(
            "API_KEY=GET_FROM_LOCAL_ENV\n"
            "DB_PASSWORD=GET_FROM_LOCAL_ENV\n"
            "JWT_SECRET=GET_FROM_LOCAL_ENV\n"
        )

        # Act
        with patch.dict(
            os.environ,
            {
                "API_KEY": "api-key-123",
                "DB_PASSWORD": "db-pass-456",
                "JWT_SECRET": "jwt-secret-789",
            },
        ):
            update_env_file_with_local_env(str(input_file), str(output_file))

        # Assert
        content = output_file.read_text()
        assert "API_KEY=api-key-123\n" in content
        assert "DB_PASSWORD=db-pass-456\n" in content
        assert "JWT_SECRET=jwt-secret-789\n" in content
        assert "GET_FROM_LOCAL_ENV" not in content

    def test_handles_empty_input_file(self, tmp_path: Path) -> None:
        """Test handling of empty input file."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text("")

        # Act
        update_env_file_with_local_env(str(input_file), str(output_file))

        # Assert
        assert output_file.exists()
        assert output_file.read_text() == ""

    def test_handles_whitespace_around_get_from_local_env(self, tmp_path: Path) -> None:
        """Test that whitespace around GET_FROM_LOCAL_ENV is handled correctly."""
        # Arrange
        input_file = tmp_path / "input.env"
        output_file = tmp_path / "output.env"
        input_file.write_text("  SPACED_VAR=GET_FROM_LOCAL_ENV  \n")

        # Act
        with patch.dict(os.environ, {"SPACED_VAR": "replaced_value"}):
            update_env_file_with_local_env(str(input_file), str(output_file))

        # Assert
        content = output_file.read_text()
        assert "SPACED_VAR=replaced_value\n" in content
