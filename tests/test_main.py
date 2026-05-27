"""Tests for the rle-python core CLI (rle.core.cli)."""

import pytest
from typer.testing import CliRunner

from rle.core.cli import app

runner = CliRunner()


@pytest.mark.unit
def test_main_no_command():
    """Test that the app prints a message when no command is provided."""
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Hello from rle-python!" in result.stdout


@pytest.mark.unit
def test_main_version():
    """Test that --version prints the version string."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "rle-python version" in result.stdout


@pytest.mark.unit
def test_backends_command_runs():
    """Test that the `backends` command runs successfully."""
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
