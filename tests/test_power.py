"""Power-state evidence, including ambiguous deep standby and timeouts."""

from unittest.mock import patch

from custom_components.philips_titanos.power import PowerEvidence, PowerState


def test_http_without_power_is_unknown():
    """Connectivity and successful commands cannot assert screen state."""
    state = PowerEvidence()
    state.observe(None)
    assert state.is_on is None
    state.requested(False)
    assert state.is_on is None
    with patch("time.monotonic", return_value=state.pending_until + 1):
        state.observe(None)
    assert state.state == PowerState.UNKNOWN
    assert state.uncertain_standby_sent


def test_confirmed_transitions():
    """A verified signal can confirm the pending transition."""
    state = PowerEvidence()
    state.observe("on")
    assert state.is_on is True
    state.requested(False)
    state.observe("on")
    assert state.state == PowerState.STANDBY_PENDING
    state.observe("standby")
    assert state.state == PowerState.QUICK_STANDBY
    assert state.is_on is False
    state.requested(True)
    state.observe("standby")
    assert state.state == PowerState.WAKING
    state.observe("on")
    assert state.is_on is True


def test_disconnect_not_deep_standby():
    """Network loss never falsely confirms off/deep standby."""
    state = PowerEvidence()
    state.observe("off")
    state.disconnected()
    assert state.state == PowerState.UNAVAILABLE
    assert state.is_on is None
    state.observe(None)
    assert state.state == PowerState.UNKNOWN
