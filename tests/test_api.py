"""Request-level JointSpace tests; no TV credentials or network required."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.philips_titanos.api import (
    ApiError,
    CannotConnect,
    InvalidAuth,
    PairingError,
    PairingSession,
    TitanOSClient,
    TitanOSError,
    wake_on_lan,
)


def client_response(text="", status=200):
    """A context manager with a real request-level response contract."""
    response = AsyncMock()
    response.status = status
    response.text.return_value = text
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request.return_value = context
    return TitanOSClient(session, "192.0.2.10", "test-device", "test-password"), session


@pytest.mark.parametrize(
    "status,error",
    [(401, InvalidAuth), (403, ApiError), (404, ApiError), (500, ApiError)],
)
async def test_http_errors(status, error):
    """Preserve auth versus unsupported endpoint semantics."""
    client, _ = client_response(status=status)
    with pytest.raises(error):
        await client.get_current_activity()


@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientConnectionError()])
async def test_network_errors(error):
    """Timeouts are normalized and not automatically retried."""
    client, session = client_response()
    session.request.return_value.__aenter__.side_effect = error
    with pytest.raises(CannotConnect):
        await client.send_key("VolumeUp")
    assert session.request.call_count == 1


@pytest.mark.parametrize("text", ["[]", "{}", "<html>ok</html>", '{"id":', '{"id":7}'])
async def test_unexpected_activity(text):
    """Malformed or nonsensical reads are not device-state evidence."""
    client, _ = client_response(text)
    with pytest.raises(TitanOSError):
        await client.get_current_activity()


async def test_key_payload_and_digest():
    """Verify method, path, key payload, timeout and authentication middleware."""
    client, session = client_response("Ok")
    await client.send_key("Confirm")
    args, kwargs = session.request.call_args
    assert args == ("POST", "https://192.0.2.10:1926/6/input/key")
    assert kwargs["json"] == {"key": "Confirm"}
    assert kwargs["middlewares"] == (client._auth,)
    assert kwargs["timeout"].total == 10


async def test_pair_logs_no_payload(caplog):
    """Debug logs never contain returned pairing secrets."""
    client, _ = client_response(
        '{"error_id":"SUCCESS","auth_key":"test-sensitive-value","timestamp":42}'
    )
    with caplog.at_level("DEBUG"):
        pairing = await client.pair_request({})
    assert pairing.timestamp == 42
    assert "test-sensitive-value" not in caplog.text


@pytest.mark.parametrize("body", ["[]", "{}", '{"error_id":"SUCCESS"}'])
async def test_bad_pairing_response(body):
    """Missing fields must not escape as KeyError or TypeError."""
    client, _ = client_response(body)
    with pytest.raises(PairingError):
        await client.pair_request({})


@pytest.mark.parametrize(
    "status,body,valid",
    [
        (200, '{"error_id":"SUCCESS"}', True),
        (200, '{"error_id":"FAIL"}', False),
        (401, "", False),
    ],
)
async def test_pair_grant(status, body, valid):
    """Valid/invalid PIN responses preserve or reject pairing credentials."""
    client, _ = client_response(body, status)
    pairing = PairingSession("test-id", "test-pending-key", 42, 30)
    if valid:
        assert await client.pair_grant(pairing, "1234") == pairing.auth_key
    else:
        with pytest.raises(PairingError):
            await client.pair_grant(pairing, "0000")
        assert client._auth is None


async def test_wol_packet():
    """Verify actual magic-packet construction, not a fake success response."""
    transport = MagicMock()
    with patch("asyncio.get_running_loop") as get_loop:
        get_loop.return_value.create_datagram_endpoint = AsyncMock(
            return_value=(transport, None)
        )
        await wake_on_lan("02:00:00:00:00:01", "192.0.2.255")
    transport.sendto.assert_called_once_with(
        b"\xff" * 6 + bytes.fromhex("020000000001") * 16
    )
    transport.close.assert_called_once()


@pytest.mark.parametrize("body", ['{"error_id":"FAIL"}', '{"error":{"code":1}}'])
async def test_key_semantic_failure(body):
    """HTTP 200 with an explicit API error must not count as acceptance."""
    client, _ = client_response(body)
    with pytest.raises(TitanOSError, match="rejected"):
        await client.send_key("Confirm")


@pytest.mark.parametrize("mac", ["00", "not-a-mac", "00112233445566"])
async def test_invalid_wol_mac(mac):
    """Refuse invalid addresses before any socket is opened."""
    with pytest.raises(ValueError):
        await wake_on_lan(mac)
