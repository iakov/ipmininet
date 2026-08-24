# Development notes

This file is `[describing]` — it explains rationale and design context.
For agent behavior rules and commands, see `AGENTS.md`.

## Version pinning strategy

`pyproject.toml` uses intentionally loose constraints (e.g. `mako>=1.1`).
`uv.lock` is the lockfile that pins exact versions. This keeps `pyproject.toml`
clean while providing reproducible builds. After any `pyproject.toml` version
adjustment, run `uv sync --all-extras --upgrade` and commit the updated
`uv.lock`.

## Type safety stance

This codebase does not use mypy. The `ConfigDict` pattern (attribute-style dict
access) is pervasive in the daemon config system and is fundamentally
un-typeable. Ruff's lint rules (25 groups) cover real error classes — undefined
names, unused imports, mutable defaults, loop variable capture — without the
annotation burden that mypy would require.

## Test suite status (Aug 2026)

All tests run in a multi-stage container (see `Containerfile`). Current results
from a clean full run:

| Metric | Value |
|--------|-------|
| Total | 148 passed, 22 failed, 4 skipped |
| Duration | ~109 min (full suite) |
| CI subset | 60 passed in ~6 min |

### Known failures (not yet fixed)

| Test file | Failure count | Root cause |
|-----------|--------------|------------|
| `test_srv6.py` | 7 | SRv6 static routing — likely kernel/config missing |
| `test_dns.py` | 6 | DNS named daemon config assertion — timing or config generation |
| `test_openr.py` | 3 | **Skip added** — OpenR build not available |
| `test_exabgp.py` | 4 | **Skip added** — ExaBGP 4.2.11 broken vendored six dependency |
| `test_link.py` | 2 | Address ordering — parametrized cases 8-9 |
| `test_sshd.py` | 1 | SSHD config check return code 255 |
| `test_iptables.py` | 1 | iptables example |
| `test_network_capture.py` | 1 | Network capture |
| `test_gre.py` | 1 | GRE tunnel |

### CI strategy

The CI runs a ~5-minute subset of fast, reliable tests: `test_address_alllocation.py`,
`test_cli.py`, and `test_misc.py`. Coverage reports are uploaded as artifacts
for manual review. The full suite can be reproduced locally via `ci-test.sh`
or `ci-diag.sh`.
