# Validation and release evidence

## Reproducible software checks

```bash
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q --junitxml=test-results.xml
```

Python 3.14.9 is pinned in `.python-version`; the development lock uses Home
Assistant 2026.10.1. CI additionally runs hassfest and HACS repository validation.
Exact results for version 1.0.0 must be taken from its CI run and JUnit output,
not copied from the preceding version. See the published release/PR checks.

The preceding 0.2.0 revision `ae0f4e67ad1c4f280cc5704fa7838cecc4e0ef8f`
passed 99 tests, Ruff, hassfest and HACS in
[run 42846542436](https://github.com/ruisilva-bit/ha-titanOS/actions/runs/42846542436).
That evidence describes the old revision only.

## Test boundaries

Tests exercise HA config/options flows, credential preservation, pairing without
Cast, HA service dispatch, default production controls and explicit opt-out,
legacy-option compatibility, DIAL discovery/launch, backoff and recovery,
malformed grants, diagnostics, request concurrency and ambiguous Standby guards.
They use simulated network clients unless a test explicitly creates a local
in-process endpoint. They do not operate the user's TV.

Local run of this revision (Python 3.14.6, `pytest`): 120 tests passed, with
`ruff check` and `ruff format --check` clean. hassfest and HACS were not run locally.

The TV panel's keys are checked against the remote service's key table, and its
buttons were driven in headless Chromium with a stub `hass` (payloads, confirmations,
layout at 390 px and desktop). Real Home Assistant frontend rendering was not run.

## Read-only hardware procedure

```bash
python3 tools/probe_tv.py TV_IP
python3 tools/probe_tv.py TV_IP --paired
```

Use only the authorized single TV address. The tool does not scan a subnet,
issue control writes, save credentials or dump bodies. Existing pairing inputs
are masked. Keep credentials, QR codes and `.storage` out of issues/chat.

For each actual screen state, record only sanitized status: TCP/TLS, authenticated
system reachability, powerstate and mute observations, DIAL registrations and
whether values track the physical remote. Reaching JointSpace does not prove
on; a network failure does not establish deep standby. DIAL `running` is not a
foreground-app signal.

## Controlled write procedure

Obtain permission first. Send a single harmless navigation/volume key and observe
its physical effect. Test mute independently. Test Standby once when interruption
is acceptable. Never retry automatically after timeout: the write may have
executed. The latch remains until a reliable subsequent on observation or a
manual integration reload after checking the screen. WOL sends intent only.
Confirm application launch and reconnect behaviour separately.

## Update and rollback

Retain the old component directory and a private HA backup. Replace only the
component folder and restart in an approved window. Keep the existing config
entry; compare unique IDs/entities and verify no pairing request occurred.
Rollback uses the complete previous folder or private HA backup, not fabricated
credential migration. Ensure HACS has a single owning repository.
