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

Current results from a clean full bare-metal run (skipping exabgp, openr):

| Metric | Value |
|--------|-------|
| Passed | 148 |
| Failed | 22 |
| Skipped | 4 (exabgp + openr, marked `@pytest.mark.skip`) |
| Duration | ~109 min (full suite) |
| Light CI subset | ~60 passed in ~2-3 min |

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

### CI architecture

Three workflows, each with a single source of truth for its config:

| Workflow | File | Trigger | Duration | What it runs |
|----------|------|---------|----------|-------------|
| Light bare-metal | `test.yaml` | push, PR | ~2-3 min | `install -a` + all non-skipped tests |
| Light container | `container-test.yaml` | push, PR | ~1-2 min | Build container + `test_misc.py` + coverage artifact |
| Heavy bare-metal | `heavy-test.yaml` | workflow_dispatch, push to master | ~110 min | `install -a` + full suite + coverage artifact |

Before opening a PR, run the full container suite locally (`scripts/ci-test.sh ipmininet/tests/`
inside a built container). This ~2-hour validation matches the heavy CI that runs on master.

### Multi-stage container design

The `Containerfile` has three stages:

1. **`deps`**: Ubuntu 24.04 + build deps + `uv sync` + cached tarballs (libyang, frr)
1. **`compile`**: Builds libyang into `/usr/` (so frrouting's `./configure` finds it via pkg-config),
   then builds frrouting with `--prefix=/opt/compiled-frr`. Copies libyang `.so` files from
   `/usr/lib/x86_64-linux-gnu/` into `/opt/compiled-frr/lib/`.
1. **`final`**: Fresh Ubuntu 24.04 with runtime deps only. `COPY --from=compile /opt/compiled-frr/ /usr/`
   - `ldconfig`. Then `uv sync` + `scripts/ci-install.sh` (mininet mnexec + exabgp + enable_ipv6 + test deps).

Key invariants:

- **Skip-if-built guards** in `install.py`: `install_libyang()` checks for `libyang.so` in the install prefix,
  `install_frrouting()` checks for `zebra` in the install prefix. This enables incremental builds with
  volume mounts.
- **`--install-frrouting-compile` flag**: Installs frrouting to `/opt/compiled-frr` (used only in the
  compile stage). The normal `-a` / `--install-frrouting` installs to `output_dir/frr` (used in
  bare-metal CI and local dev).
- **Tests requiring switches** need `ovsdb-server` and `ovs-vswitchd` running manually (no `systemctl`
  in containers). Handled by `scripts/ci-test.sh` and `scripts/ci-diag.sh`.

### Externally-sourced daemons

| Daemon | Status | Reason |
|--------|--------|--------|
| FRRouting 7.5 + libyang 1.0.215 | Working, pinned | Built in compile stage, cached by GHA |
| ExaBGP 4.2.11 | `@pytest.mark.skip` | Vendored `six` broken on Python 3.12 |
| OpenR | `@pytest.mark.skip` | External build requires ~4GB RAM, not available in CI |
