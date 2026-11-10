#!/usr/bin/env python3
"""Read-only single-host Titan OS probe. No scans, pairing or control writes.

Run in a trusted local terminal. --paired asks for existing credentials using
masked input; nothing is persisted. Output never contains raw API bodies.
"""

import argparse
import getpass
import json
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPDigestAuthHandler,
    HTTPPasswordMgrWithDefaultRealm,
    HTTPSHandler,
    Request,
    build_opener,
)
import xml.etree.ElementTree as ET


def probe(host: str, paired: bool = False) -> dict:
    """Inspect documented endpoints only, sequentially and with bounded timeouts."""
    # IP/hostname only, never URLs that could leak credentials or change scope.
    if any(c in host for c in "/@?#:"):
        raise ValueError("Supply a hostname or IPv4 address, not a URL")
    base = f"https://{host}:1926/6"
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # JointSpace self-signed certificate.
    manager = HTTPPasswordMgrWithDefaultRealm()
    if paired:
        username = getpass.getpass("Existing JointSpace device ID (masked): ")
        password = getpass.getpass("Existing JointSpace auth key (masked): ")
        manager.add_password(None, base, username, password)
    opener = build_opener(HTTPSHandler(context=context), HTTPDigestAuthHandler(manager))
    result = {
        "read_only": True,
        "screen_power_verified": False,
        "ports": {},
        "reads": {},
    }
    for port in (1926, 8009, 8883, 56789, 56790):
        try:
            with socket.create_connection((host, port), timeout=2):
                result["ports"][str(port)] = "reachable_not_functionally_validated"
        except OSError:
            result["ports"][str(port)] = "unreachable_or_filtered"
    endpoints = [("system", base + "/system", None)]
    if paired:
        endpoints.extend(
            (path, base + "/" + path, None)
            for path in (
                "powerstate",
                "screenstate",
                "activities/current",
                "audio/volume",
                "ambilight/supportedstyles",
                "network/devices",
            )
        )
    if result["ports"]["56789"].startswith("reachable"):
        endpoints.extend(
            ("dial_" + app, f"http://{host}:56789/apps/{app}", origin)
            for app, origin in (
                ("YouTube", "https://www.youtube.com"),
                ("Netflix", "https://www.netflix.com"),
                ("AmazonInstantVideo", None),
            )
        )
    for name, url, origin in endpoints:
        time.sleep(0.8)
        try:
            request = Request(url, headers={"Origin": origin} if origin else {})
            with opener.open(request, timeout=8) as response:
                body = response.read(65536)
                row = {"http_status": response.status}
            if name.startswith("dial_"):
                root = ET.fromstring(body)
                row["reported_app_state"] = next(
                    (
                        e.text
                        for e in root.iter()
                        if e.tag.rsplit("}", 1)[-1] == "state"
                    ),
                    None,
                )
            else:
                data = json.loads(body)
                if isinstance(data, dict):
                    if name in ("powerstate", "screenstate"):
                        # These values need visual cross-check; they may be stale.
                        value = data.get(name)
                        if isinstance(value, str) and value.casefold() in (
                            "on",
                            "off",
                            "standby",
                        ):
                            row["reported_not_verified"] = value
                    row["json_type"] = "object"
                else:
                    row["json_type"] = type(data).__name__
            result["reads"][name] = row
        except HTTPError as err:
            result["reads"][name] = {"http_status": err.code}
        except URLError, OSError, ValueError, ET.ParseError:
            result["reads"][name] = {"error": "timeout_connection_or_invalid_response"}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--paired", action="store_true")
    args = parser.parse_args()
    print(json.dumps(probe(args.host, args.paired), indent=2))
