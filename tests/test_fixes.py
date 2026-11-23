# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Regression tests for the review fixes in the 1.0.x line."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from custom_components.philips_titanos.api import CannotConnect, find_menu_node
from custom_components.philips_titanos.config_flow import _wol_mac
from custom_components.philips_titanos.coordinator import TitanOSCoordinator
from homeassistant.components.remote import (
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import HOST, MAC, MENU

ROOT = Path(__file__).parents[1]
TRANSLATIONS = ROOT / "custom_components/philips_titanos/translations"
ENTITY_ID = "remote.43pus8400_12"


def _flat_keys(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flat_keys(value, path)
        else:
            keys.add(path)
    return keys


def _load(lang: str) -> dict:
    return json.loads((TRANSLATIONS / f"{lang}.json").read_text(encoding="utf-8"))


def test_translations_have_same_keys() -> None:
    """Every locale must define every string the English source defines."""
    english = _flat_keys(_load("en"))
    assert _flat_keys(_load("pt")) == english
    assert _flat_keys(_load("de")) == english


def test_portuguese_is_actually_portuguese() -> None:
    """Regression: pt.json was a byte copy of the English file."""
    pt = _load("pt")
    assert pt != _load("en")
    assert pt["config"]["abort"]["already_configured"] == (
        "O dispositivo já está configurado"
    )


async def test_ambilight_menu_retried_after_partial_failure() -> None:
    """A failed menu read must not leave styles without menu nodes."""
    coordinator = TitanOSCoordinator.__new__(TitanOSCoordinator)
    coordinator.ambilight_styles = []
    coordinator.ambilight_menu = {}
    coordinator.ambilight_off_node = None
    coordinator.client = AsyncMock()
    coordinator.client.get_ambilight_styles.return_value = [
        {"styleName": "FOLLOW_VIDEO", "algorithms": ["STANDARD"]}
    ]
    coordinator.client.get_menu_structure.side_effect = [CannotConnect("timeout"), MENU]

    with pytest.raises(CannotConnect):
        await coordinator._async_fetch_ambilight()
    assert coordinator.ambilight_styles == []

    await coordinator._async_fetch_ambilight()
    assert coordinator.ambilight_styles
    assert (
        coordinator.ambilight_off_node
        == (find_menu_node(MENU, "ambilight_off")["node_id"])
    )
    assert coordinator.client.get_menu_structure.await_count == 2


def test_wol_mac_skips_malformed_entries() -> None:
    """Regression: an interface without a MAC raised KeyError during pairing."""
    devices = [
        {"wake-on-lan": "Enabled"},
        {"wake-on-lan": "Enabled", "mac": "not-a-mac"},
        {"wake-on-lan": "Enabled", "mac": "02:00:00:00:00:02"},
    ]
    assert _wol_mac(devices, "192.0.2.99") == "02:00:00:00:00:02"


def test_wol_mac_prefers_the_tv_address() -> None:
    devices = [
        {"wake-on-lan": "Enabled", "mac": "02:00:00:00:00:02", "ip": "192.0.2.99"},
        {"wake-on-lan": "Enabled", "mac": MAC, "ip": HOST},
    ]
    assert _wol_mac(devices, HOST) == MAC


def test_wol_mac_none_without_wake_on_lan() -> None:
    assert _wol_mac([{"mac": MAC, "wake-on-lan": "Disabled"}], HOST) is None


async def _send(hass: HomeAssistant, **data: object) -> None:
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )


@pytest.mark.usefixtures("init_integration")
async def test_unknown_key_sends_nothing(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Regression: a bad name after a valid one sent a partial sequence."""
    with pytest.raises(ServiceValidationError):
        await _send(hass, command=["CursorUp", "NotAKey"])
    mock_client.send_key.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_aliases_are_case_insensitive(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    await _send(hass, command=["OK", "cursorup"])
    assert [c.args[0] for c in mock_client.send_key.await_args_list] == [
        "Confirm",
        "CursorUp",
    ]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "data",
    [{"num_repeats": 11}, {"delay_secs": 3.0}],
    ids=["too_many_repeats", "too_long_delay"],
)
async def test_repeats_and_delay_are_bounded(
    hass: HomeAssistant, mock_client: AsyncMock, data: dict
) -> None:
    with pytest.raises(ServiceValidationError):
        await _send(hass, command=["CursorUp"], **data)
    mock_client.send_key.assert_not_awaited()
