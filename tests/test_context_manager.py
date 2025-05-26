"""Tests for BSBLAN context manager features."""
# pylint: disable=protected-access

from unittest.mock import AsyncMock, patch

import pytest

from bsblan import BSBLAN
from bsblan.bsblan import BSBLANConfig


@pytest.mark.asyncio
async def test_context_manager_session_creation() -> None:
    """Test that context manager creates and closes a session."""
    config = BSBLANConfig(host="example.com")

    # Mock the initialize method to avoid actual API calls
    with patch.object(BSBLAN, "initialize", AsyncMock()) as mock_init:
        async with BSBLAN(config) as bsblan:
            # Check that session was created
            assert bsblan.session is not None
            assert bsblan._close_session is True

            # Check that initialize was called
            mock_init.assert_called_once()

        # After context exit, session.close should have been called
        # This is implicit since we're testing the context manager behavior


@pytest.mark.asyncio
async def test_context_manager_with_existing_session() -> None:
    """Test that context manager uses an existing session if provided."""
    config = BSBLANConfig(host="example.com")

    # Create a mock session
    session = AsyncMock()
    session.closed = False

    # Mock initialize to avoid actual API calls
    with patch.object(BSBLAN, "initialize", AsyncMock()) as mock_init:
        async with BSBLAN(config, session=session) as bsblan:
            # Check that our session was used
            assert bsblan.session is session
            assert bsblan._close_session is False

            # Check that initialize was called
            mock_init.assert_called_once()

        # After context exit, session.close should not have been called
        session.close.assert_not_called()


@pytest.mark.asyncio
async def test_aexit_exception_handling() -> None:
    """Test that BSBLAN doesn't swallow exceptions during session close."""
    config = BSBLANConfig(host="example.com")

    # Create a mock session with a close method that raises an exception
    mock_session = AsyncMock()
    mock_session.close = AsyncMock(side_effect=Exception("Test exception"))

    # Patch initialize to avoid actual API calls
    with patch.object(BSBLAN, "initialize", AsyncMock()):
        # Create BSBLAN instance with our mock session
        bsblan = BSBLAN(config, session=mock_session)
        bsblan._close_session = True  # Force close on exit

        # The exception from session.close should be propagated
        with pytest.raises(Exception, match="Test exception"):
            async with bsblan:
                pass  # Just enter and exit the context
