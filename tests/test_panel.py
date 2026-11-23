# Modified by Alex for ha-titanOS; derived from ksooo/ha-philips-titanos.
# Upstream code is Apache-2.0: see LICENSE.upstream and NOTICE.
"""Tests for the sidebar TV panel that the integration registers itself."""

from pathlib import Path
import re

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_titanos.const import DOMAIN
from custom_components.philips_titanos.panel import (
    FRONTEND_DIR,
    MODULE_NAME,
    PANEL_COMPONENT,
    STATIC_URL,
    panel_url_path,
)
from custom_components.philips_titanos.remote import _resolve_key
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import SERIAL

REMOTE = "remote.43pus8400_12"
PLAYER = "media_player.43pus8400_12"
JS = FRONTEND_DIR / MODULE_NAME


def _panel(hass: HomeAssistant, entry: MockConfigEntry):
    return hass.data[DATA_PANELS].get(panel_url_path(entry))


async def test_panel_registered_with_this_tvs_entities(
    hass: HomeAssistant, init_integration, config_entry: MockConfigEntry
) -> None:
    """The panel appears in the sidebar bound to the real entity IDs."""
    panel = _panel(hass, config_entry)
    assert panel is not None
    assert panel.component_name == "custom"
    assert panel.sidebar_title == config_entry.title
    custom = panel.config["_panel_custom"]
    assert custom["name"] == PANEL_COMPONENT
    assert custom["module_url"] == f"{STATIC_URL}/{MODULE_NAME}"
    assert panel.config["remote"] == REMOTE
    assert panel.config["player"] == PLAYER


async def test_panel_removed_on_unload(
    hass: HomeAssistant, init_integration, config_entry: MockConfigEntry
) -> None:
    """Unloading or reloading the entry must not leave a stale sidebar item."""
    assert _panel(hass, config_entry) is not None
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _panel(hass, config_entry) is None


async def test_panel_survives_reload(
    hass: HomeAssistant, init_integration, config_entry: MockConfigEntry
) -> None:
    """A reload re-registers the same URL without a duplicate-panel error."""
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _panel(hass, config_entry) is not None


def test_panel_url_is_stable_and_url_safe() -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SERIAL)
    url = panel_url_path(entry)
    assert url == panel_url_path(entry)
    assert re.fullmatch(r"[a-z0-9-]+", url)
    assert url.startswith("philips-titanos-")


def test_panel_module_is_shipped() -> None:
    assert JS.is_file()
    assert "customElements.define" in JS.read_text(encoding="utf-8")
    assert STATIC_URL.startswith("/")


def test_panel_commands_are_registered_remote_keys() -> None:
    """Every key the panel sends must pass the same validation as the service."""
    source = JS.read_text(encoding="utf-8")
    commands = set(re.findall(r'cmd\("[^"]*",\s*(?:"[^"]*"|null),\s*"(\w+)"\)', source))
    commands |= set(re.findall(r'"(\w+Colour)"', source))
    commands |= {f"Digit{i}" for i in range(10)}
    commands.add("Standby")
    assert len(commands) >= 25
    for command in commands:
        if command == "Standby":
            continue
        assert _resolve_key(command) == command, command


async def test_panel_key_reaches_tv_through_remote_entity(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    """A panel key reaches the TV through the remote entity and the key check."""
    await hass.services.async_call(
        "remote",
        "send_command",
        {"entity_id": REMOTE, "command": ["CursorUp"]},
        blocking=True,
    )
    mock_client.send_key.assert_awaited_once_with("CursorUp")


async def test_panel_unknown_key_is_rejected(
    hass: HomeAssistant, init_integration, mock_client
) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "remote",
            "send_command",
            {"entity_id": REMOTE, "command": ["Nope"]},
            blocking=True,
        )
    mock_client.send_key.assert_not_awaited()


def test_frontend_dir_is_inside_integration() -> None:
    assert Path(FRONTEND_DIR).is_dir()
