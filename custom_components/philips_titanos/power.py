"""Conservative power evidence, independent of HTTP and Cast reachability."""

from dataclasses import dataclass
from enum import StrEnum
import time


class PowerState(StrEnum):
    """Only explicit observations may establish a screen state."""

    UNKNOWN = "unknown"
    ON = "on"
    STANDBY_PENDING = "standby_pending"
    QUICK_STANDBY = "quick_standby"
    DEEP_STANDBY = "deep_standby"
    WAKING = "waking"
    UNAVAILABLE = "unavailable"


@dataclass
class PowerEvidence:
    """Commands record intent, never proof of execution.

    An unreachable device is not proof of deep standby: unplugging and network
    failure look identical. DEEP_STANDBY is reserved for a future explicit signal.
    """

    state: PowerState = PowerState.UNKNOWN
    pending_until: float = 0
    uncertain_standby_sent: bool = False

    @property
    def is_on(self) -> bool | None:
        """Translate evidence to HA's nullable power state."""
        if self.state == PowerState.ON:
            return True
        if self.state in (PowerState.QUICK_STANDBY, PowerState.DEEP_STANDBY):
            return False
        return None

    def observe(self, value: str | None) -> None:
        """Apply a caller-validated power signal, or keep uncertainty."""
        now = time.monotonic()
        if now < self.pending_until:
            if self.state == PowerState.WAKING and value != "on":
                return
            if self.state == PowerState.STANDBY_PENDING and value not in (
                "standby",
                "off",
            ):
                return
        if value == "on":
            self.state = PowerState.ON
            self.uncertain_standby_sent = False
        elif value in ("standby", "off"):
            self.state = PowerState.QUICK_STANDBY
            self.uncertain_standby_sent = False
        else:
            self.state = PowerState.UNKNOWN
        self.pending_until = 0

    def requested(self, on: bool) -> None:
        """Latch power intent so a toggle cannot be resent on an unknown screen."""
        self.state = PowerState.WAKING if on else PowerState.STANDBY_PENDING
        self.pending_until = time.monotonic() + (45 if on else 20)
        # WOL does not clear the standby latch; only observed state does.
        if not on:
            self.uncertain_standby_sent = True

    def disconnected(self) -> None:
        """Never label transport failure as power off."""
        self.state = PowerState.UNAVAILABLE
