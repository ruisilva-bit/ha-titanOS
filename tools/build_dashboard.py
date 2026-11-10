"""Generate a native Home Assistant remote card without frontend dependencies."""

import argparse
from pathlib import Path
import re

import yaml


def build_card(remote: str, player: str) -> dict:
    """Use actual entity IDs; never register or expose a new service."""
    if not re.fullmatch(r"remote\.[a-z0-9_]+", remote):
        raise ValueError("Expected a remote entity ID")
    if not re.fullmatch(r"media_player\.[a-z0-9_]+", player):
        raise ValueError("Expected a media_player entity ID")

    def button(name, icon, key=None, service=None, confirmation=False):
        action = {
            "action": "perform-action",
            "perform_action": service or "remote.send_command",
            "target": {"entity_id": remote},
        }
        if key:
            action["data"] = {"command": [key], "num_repeats": 1, "delay_secs": 0.3}
        if confirmation:
            action["confirmation"] = {
                "title": "TV power",
                "text": "Send this power command to the TV?",
                "confirm_text": "Send command",
                "dismiss_text": "Cancel",
            }
        return {
            "type": "button",
            "name": name,
            "icon": "mdi:" + icon,
            "show_state": False,
            "icon_height": "28px",
            "tap_action": action,
            "hold_action": {"action": "none"},
            "double_tap_action": {"action": "none"},
        }

    def grid(buttons, columns=3):
        return {"type": "grid", "columns": columns, "square": False, "cards": buttons}

    blank = {
        "type": "button",
        "show_name": False,
        "show_icon": False,
        "tap_action": {"action": "none"},
        "hold_action": {"action": "none"},
    }
    cards = [
        {
            "type": "markdown",
            "content": "## Philips TV Remote\nLocal control · Titan OS",
        },
        grid(
            [
                button("Wake", "power-on", service="remote.turn_on", confirmation=True),
                button("Sources", "video-input-hdmi", "Source"),
                button(
                    "Standby",
                    "power-standby",
                    service="remote.turn_off",
                    confirmation=True,
                ),
            ]
        ),
        grid(
            [
                button("Home", "home", "Home"),
                button("Back", "arrow-u-left-top", "Back"),
                button("Options", "dots-horizontal", "Options"),
            ]
        ),
        grid(
            [
                blank,
                button("Up", "chevron-up", "CursorUp"),
                blank,
                button("Left", "chevron-left", "CursorLeft"),
                button("OK", "checkbox-marked-circle-outline", "Confirm"),
                button("Right", "chevron-right", "CursorRight"),
                blank,
                button("Down", "chevron-down", "CursorDown"),
                blank,
            ]
        ),
        grid(
            [
                button("Volume -", "volume-minus", "VolumeDown"),
                button("Mute", "volume-mute", "Mute"),
                button("Volume +", "volume-plus", "VolumeUp"),
            ]
        ),
        grid(
            [
                button("Channel -", "minus", "ChannelStepDown"),
                button("Info", "information-outline", "Info"),
                button("Channel +", "plus", "ChannelStepUp"),
            ]
        ),
        grid(
            [
                button("Rewind", "rewind", "Rewind"),
                button("Play", "play", "Play"),
                button("Pause", "pause", "Pause"),
                button("Stop", "stop", "Stop"),
                button("Forward", "fast-forward", "FastForward"),
                button("Live TV", "television", "WatchTV"),
            ]
        ),
        grid(
            [
                button(str(i), "numeric-" + str(i), "Digit" + str(i))
                for i in (*range(1, 10), 0)
            ]
        ),
        grid(
            [
                button(name, "circle", key) | {"color": name.lower()}
                for name, key in (
                    ("Red", "RedColour"),
                    ("Green", "GreenColour"),
                    ("Yellow", "YellowColour"),
                    ("Blue", "BlueColour"),
                )
            ],
            4,
        ),
        {"type": "media-control", "entity": player},
    ]
    return {"type": "vertical-stack", "cards": cards}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="remote.your_tv")
    parser.add_argument("--player", default="media_player.your_tv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = yaml.safe_dump(
        build_card(args.remote, args.player), sort_keys=False, allow_unicode=True
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
