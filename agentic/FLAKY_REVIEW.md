# FLAKY_REVIEW — flaky-test pattern catalog & audit guide

This document is a runnable catalog of the flaky-test patterns found (and
fixed) in ipmininet's test suite. Its purpose is to give a **review agent**
(human or automated) a precise, grep-able checklist to audit tests and PRs
for flakiness, and to direct fixes to the blessed polling helper
`ipmininet/tests/utils.py::wait_until` (and the existing poll helpers built
on it: `assert_routing_table`, `assert_dns_record`, `assert_stp_state`,
`assert_connectivity`, `check_tcp_connectivity`, `traceroute`, plus
`test_exabgp.py::wait_for_expected_routes`).

Core principle:

> **Never wait for a fixed wall-clock amount of time for an asynchronous
> effect (daemon startup, routing/BGP/zone convergence, packet flush).
> Poll for the observable effect until it appears, with a hard timeout.**

---

## How to audit

Run each pattern's `rg` signature below, then classify each hit:

- **FIX** — violates a pattern; rewrite using `wait_until`/a poll helper.
- **OK** — a bounded poll loop already (check-then-sleep, hard timeout).
- **BY DESIGN** — tiny jitter between two dependent actions within a poll
  loop (e.g. `time.sleep(0.5)` inside a bounded retry loop); acceptable if
  the loop has a hard bound and re-checks the condition.

Report findings as `file:line -> pattern -> verdict -> suggested fix`.

---

## P1 — Fixed wall-clock sleep before asserting async state

Why flaky: the wait is either too short (assertion runs before the effect
lands — intermittent CI failures under load) or too long (slow for no
reason). Under parallel xdist load every daemon start / convergence gets
slower, so a "generous" fixed sleep is still a race.

Signature:

```bash
rg -n "time\.sleep\(\s*[0-9]" ipmininet/tests/
```

Repo examples (fixed in PR #24 / the anti-flaky PR):
- `test_exabgp.py` — `time.sleep(130)` then RIB check → **the** CI flake
  (`KeyError: '8.8.0.0/24'`); root cause ExaBGP `passive` + `tcp.delay=2`
  (see P7). Fixed by polling.
- `test_ripng.py:180` `time.sleep(10)` before `assert_routing_table(...,
  present=False)` — redundant: the helper already polls.
- `test_dns.py:116,166` `time.sleep(10)` between record batches.
- `test_srv6.py:72,79` `time.sleep(15)` / `time.sleep(1)` for tshark.
- `test_tc.py:52` `time.sleep(1)` before the iperf3 client.
- `test_iptables.py:32` `time.sleep(5)` in a coarse poll loop.

Fix: replace with `wait_until(predicate, timeout=..., interval=...,
description=...)`, or a higher-level poll helper. Acceptance: no
`time.sleep(<literal> ...)` in tests whose purpose is "wait for X".

---

## P2 — Single-shot assert right after a blocking cmd/popen (no poll)

Why flaky: the command succeeded but the observable state it produces (RIB
contents, routing table, DNS answer, TCP server) has not settled yet.

Signature:

```bash
rg -n "\.wait\(\)|\.communicate\(\)" ipmininet/tests/
```

then inspect each for a following **immediate** assertion on derived state.
Repo example: old `test_exabgp.py::check_correct_rib` ran `nc` + `wait()` and
asserted on the parsed RIB immediately; if the RIB had not converged it
failed (see P3 for the masking bug).

Fix: wrap the read+check in a `wait_until` predicate (re-run the read each
poll), keep the final one-shot assert after convergence is ensured.

---

## P3 — Deref/index before existence assert (masks the real failure)

Why flaky: a missing key/row throws `KeyError`/`IndexError` instead of the
intended assertion message, hiding whether the problem is "state not ready"
(flake) or "wrong state" (real bug).

Signature:

```bash
rg -n "\[[^]]+\]\[" ipmininet/tests/      # indexing immediately after a dict get
rg -n "rib_routes\[" ipmininet/tests/test_exabgp.py
```

Repo example: old `check_correct_rib` did `rib_routes[str_ipnet][0]` **before**
`assert str_ipnet in rib_routes`; the CI failure surfaced as a bare
`KeyError: '8.8.8.0/24'` (fixed in PR #24).

Fix: assert membership first, then index. Acceptance: every `x[k][...]` is
preceded by `assert k in x`.

---

## P4 — Unbounded / fragile poll loops (float equality, `!=` bounds)

Why flaky: a loop whose bound is `!=` (or float equality) can run forever if
the counter ever skips the sentinel — burning the whole CI budget instead of
failing fast.

Signature:

```bash
rg -n "while t != |while.*!=\s*[a-z]+ / |t != timeout" ipmininet/tests/
```

Repo examples:
- `tests/utils.py::traceroute` `while t != timeout / poll` — `timeout/poll`
  is a float; if non-integral the loop never terminates.
- `tests/utils.py::assert_connectivity` `while t != attempts` — int/int, safe
  but fragile style.
- `tests/utils.py::check_tcp_connectivity` `while t != timeout * 2`.

Fix: use `while t < bound`, or better, `wait_until`. Acceptance: no `!=`
loop sentinels; every loop has a `<` bound and a hard timeout.

---

## P5 — Shared hard-coded resources (files, ports, names) across tests/workers

Why flaky: parallel parametrized cases or workers collide on `/tmp` files and
fixed port numbers; a stale file from a previous run can be read before the
new one is written. (Mitigated in CI by `scripts/py-unshare.sh` giving each
worker a private `/tmp` + netns, but a single worker still reuses paths
across parametrized cases, and local bare runs are un-isolated.)

Signature:

```bash
rg -n '"/tmp/|/tmp/' ipmininet/tests/ | rg -v "tmpfs|py-unshare"
rg -n "server_port=|port=|:80\b|:53\b|:5201\b" ipmininet/tests/
```

Repo examples:
- `test_dns.py` reads `/tmp/named_master2.cfg`, `/tmp/named_master2.test.org.zone.cfg`
  right after `net.start()`.
- `test_srv6.py` `/tmp/{n.name}.pcap`; `test_exabgp.py`
  `/tmp/_get_{family}_rib.sh`; `test_sshd.py` `/tmp/sshd_r2.cfg`.
- `test_iptables.py` uses fixed `server_port` 80/1480/2000 for `nc`.

Fix: prefer per-test unique temp paths (`tempfile.mkdtemp()`), and wait for
the resource to be (re)created (P1) rather than assuming the previous run
cleaned up. For ports, note the netns isolation in CI; prefer ephemeral ports
where the daemon allows.

---

## P6 — Sleep-before-external-process-start (tshark, iperf3, sshd, nc)

Why flaky: a helper daemon (packet capture, bandwidth server, ssh) may not be
ready when the "wait" elapses under load; the subsequent step then fails or,
worse, silently captures nothing.

Signature:

```bash
rg -n "sleep.*[Ww]ait|Wait for" ipmininet/tests/
```

Repo examples:
- `test_srv6.py:72` `time.sleep(15)  # Wait for tshark to start`.
- `test_tc.py:52` `time.sleep(1)` before iperf3 client connects.

Fix: poll readiness — but see P10: "process is alive" is a *proxy* and can be
wrong; prefer the helper's own readiness notification. `test_gre.py` /
`test_sshd.py` show the correct bounded-poll shape.

---

## P7 — Ignoring a daemon's internal async delay

Why flaky: the product under test intentionally delays state (e.g. ExaBGP is
configured `passive` with `tcp.delay=2` → waits up to 2 min before sending
UPDATEs). A fixed sleep tuned to the *happy path* is a race by construction.

Signature: inspect test topologies for daemon options that introduce delays,
then check the test waits on the **effect**, not the wall clock:

```bash
rg -n "delay|passive|hold|timer|interval" ipmininet/examples ipmininet/router/config
```

Repo example: ExaBGP `passive=True` + `tcp.delay=2` → `test_exabgp.py` slept
130s. Fix: `wait_for_expected_routes` polls the FRR RIB.

---

## P10 — Readiness check waits on a *proxy* of the effect, not its notification

Why flaky: the readiness predicate checks something correlated but not
sufficient — a process is *alive* (`p.poll() is None`), a file *exists*,
a port is *reachable* — yet the effect that the next step depends on has not
landed. The subsequent step then silently measures nothing or fails.

This is exactly what happened when the anti-flaky PR converted srv6's fixed
sleep to `wait_until(all(p.poll() is None))`: a freshly-spawned `tshark` is
alive before it attaches to the interface, so the measurement ping was fired
before any capture was live → 7/7 srv6 failures on CI (empty pcaps →
`KeyError: 'fc00:0:d::1'`).

Signature:

```bash
rg -n "poll\(\) is None|isfile\(|getsize\(|>= 0" ipmininet/tests/
```

Repo example: `test_srv6.py` — waiting for each tshark's stderr line
`Capturing on ...` is *still* a proxy: tshark prints it before the capture is
functionally live (measured ~0.26s in the container; more under CI load), so
a single measurement ping fired right after was missed (empty pcaps →
`KeyError: 'fc00:0:d::1'`) on both CI jobs, even though the first attempt
(waiting only for `p.poll() is None`) failed the same way. A pcap file with
`size > 0` is likewise a proxy (pcapng writes its header immediately, so
size≠live capture).

Fix: the readiness condition must be the event that makes the next step safe.
For tshark the reliable notification is the capture file *growing past the
header* (packets are being written): probe until every node's pcap has grown
past a baseline taken at start, then send the single measurement probe and
stop with `SIGINT` (which flushes the captures) before asserting in the
read-back that the measurement landed. Never require off-path nodes to record
the measurement (they never see it). When several probes are recorded, group
the observations per probe by time gap (probes are well apart, a single
probe's captures span a few ms) or the inferred path repeats once per probe.
Never use "the process is still running" as readiness.

---

## P11 — Readiness probe perturbs the resource being measured

Why flaky: the probe used to check readiness consumes the very resource the
test then measures. `test_tc` probed the iperf3 server with `nc -z`; but the
server runs `iperf3 -s --one-off`, which accepts exactly one connection — the
probe consumed it, the real client got nothing, and `intervals` was empty →
2/2 tc failures on CI.

Signature:

```bash
rg -n "nc -z|nc .*-w .*5201|:5201" ipmininet/tests/
```

Repo example: `test_tc.py::assert_bw` — replaced `nc -z` with a passive
observation of the OS listening socket: `wait_until(lambda: ":5201" in
dst.cmd("ss -ltn"))`. Passive probes (`ss`, `ip route show`) perturb nothing.

Fix: check that the *server's* notification exists (listening socket in
`ss -ltn`, a pidfile, a log line) without touching the server. If the server
accepts a limited number of connections, never probe it with a real connect.

---

## P12 — Poll timeout ignores the protocol's documented worst case

Why flaky: a poll timeout tuned to the median happy path fails whenever a
documented internal delay stacks with CI load. ExaBGP is configured
`tcp.delay=2` (up to 120 s before it sends UPDATEs; FRR denies routes learned
too early) and `passive=True` (waits for FRR's Open), so the RIB fills only
after ≥~2 min; under load the delivery tail exceeds 300 s. A fixed 300 s poll
timeout then fails *after* a long, fully-deterministic wait.

Signature:

```bash
rg -n "timeout=[0-9]{3}" ipmininet/tests/test_exabgp.py
rg -n "pytest.mark.timeout" ipmininet/tests/
```

Repo example: `test_exabgp.py` — `wait_for_expected_routes` default timeout
went `300 → 540` (anti-flaky PR) and was later hardened to **`900`** by `0ee53cb`
(120 s floor + slow-delivery margin observed up to ~9 min under load); the
parametrized test is marked `@pytest.mark.timeout(1200)` so pytest-timeout's
600 s ceiling does not kill the legitimately-long wait.

Fix: size poll timeouts from the *documented worst case* of the protocol, not
the observed median; when that exceeds the project-wide `pytest-timeout`
ceiling, raise the ceiling for that test only with
`@pytest.mark.timeout(...)`.

---

## P8 — Kernel / shared-state races (iptables locks, interface churn vs daemons)

Why flaky: mutating global kernel state (iptables/xtables, interface
addresses) races with other mutators (restore processes, routing daemons
enqueuing dataplane changes). Symptoms: `Failed to enqueue dataplane
install`, `xtables lock held`, routes briefly missing.

Signature:

```bash
rg -n "iptables|xtable|up\(.*restore|restore.*address|setIP" ipmininet/
```

Repo history:
- iptables xtables-lock waits: commits `0c38e83`, `0b85e87`, `5079424`.
- `test_randomFailure[3]` flake (PR #18): `IPIntf.up(restore=True)` churned
  every address on a link flap (IPv6 dropped by kernel), racing zebra/ospfd;
  fixed by restoring only missing addresses.

Fix (tests): after any link/address/iptables mutation, poll the *converged*
state (routing table via `assert_routing_table`, path via `assert_path`,
connectivity via `assert_connectivity`) with the mutation's own completion
confirmed first (`p.wait()` on `iptables-restore`).

---

## P9 — No per-test timeout (a hang burns the CI budget)

Why flaky: a genuinely stuck test (blocked subprocess, unbounded loop, hung
daemon) consumes the 170-minute CI `test` job instead of failing fast with a
stack.

Signature:

```bash
rg -L "timeout|wait_until" ipmininet/tests/*.py   # tests with no wait/timeout
```

Repo state: `pytest-timeout` is enabled project-wide
(`[tool.pytest.ini_options] timeout = 600`), so a per-test hang now fails in
10 minutes. Keep per-poll helper timeouts (`timeout=` on `wait_until`,
`assert_routing_table`, ...) comfortably below it.

Fix: rely on `pytest-timeout`; ensure poll helpers always take a bounded
`timeout`; never leave an unbounded `while True` that `break`s only on
success.

---

## Blessed patterns to reuse (do not reinvent)

- `wait_until(predicate, *, timeout, interval=0.5, description)`
  `tests/utils.py` — the single primitive: check-then-sleep, hard-bounded,
  `pytest.fail` on timeout. `description` may be a callable evaluated at
  timeout so it can include the last observed state.
- `assert_routing_table(router, prefixes, present, timeout)` — polls `ip
  route` for prefix presence/absence.
- `assert_dns_record(node, server, record, port, timeout)` — polls `dig`.
- `assert_stp_state(switch, states, timeout)` — polls `brctl showstp`.
- `assert_connectivity(net, v6, attempts)` / `check_tcp_connectivity(...)` —
  polls reachability / TCP.
- `traceroute` / `assert_path` — polls until the path is stable N consecutive
  times.
- `test_exabgp.py::wait_for_expected_routes` — polls the FRR BGP RIB.

Audit rule: a new poll loop should be an expression on top of `wait_until`,
not a hand-rolled `while`/`time.sleep` loop.

---

## Repo flake history (context for reviewers)

| Flake | Root cause | Fix |
|---|---|---|
| `test_exabgp` `KeyError` (PR #24) | 130s fixed sleep vs ExaBGP passive+delay | poll RIB via `wait_for_expected_routes` |
| `test_srv6` 7×7 CI (anti-flaky PR) | wait_until(p.poll() is None) is a *proxy*: tshark alive ≠ capturing; even `Capturing on ...` is printed before the capture is live; a later attempt required *every* node (incl. off-path hosts) to record the measurement | probe until every pcap grows past its header (live), send one measurement, SIGINT-flush, assert it landed in the read-back; group observations per probe by time gap (P10) |
| `test_tc` 2×2 CI (anti-flaky PR) | `nc -z` probe consumed the `iperf3 --one-off` single connection | passive `ss -ltn` check (P11) |
| `test_exabgp` bare-metal delivery tail (anti-flaky PR) | RIB fills after ≥120 s by design; 300 s poll too tight under load | timeout 300→540, later hardened to 900 (`0ee53cb`) + `@pytest.mark.timeout(1200)` (P12) |
| `test_randomFailure[3]` (PR #18) | `up(restore=True)` churned addresses racing zebra/ospfd | restore only missing addrs |
| iptables flakiness | xtables lock / restore completion | wait for lock + completion (3 commits) |
| OSPF after link restore | no reconvergence wait | `74a6bc8` added wait |
| `test_iptables` IPv4 ping (audit 2026-09-04) | single-shot ping right after `net.start()` (P2) — a first packet can drop under load even when not blocked | polled with `wait_until` (mirrors the IPv6-blocked check below it); merged as #40 |

## Last audit (2026-09-04) — latent P1–P12 sweep

Ran the ready-to-run audit block against the current suite; everything else
already follows the blessed poll patterns:

- **P1** hits are all inside bounded poll loops (`utils.py` `host_connected`/
  `assert_connectivity`/`check_tcp_connectivity`) or are deliberate timing in
  a unit test (`test_network_capture.py` growth-between-polls). No unbounded
  fixed sleeps remain.
- **P2** — one genuine hit fixed: `test_iptables.py` asserted a single IPv4
  ping right after `net.start()` while the sibling IPv6-blocked check was
  already polled. Now polled with `wait_until` (rc 0 within 30 s). Merged as
  **PR #40** (`2e518a4`).
- **P3** — `test_exabgp.py:250` `rib_routes[str_ipnet][0]` is correctly
  preceded by `assert str_ipnet in rib_routes`; `test_tc.py` guards `intervals`
  before indexing each `sample["sum"]`.
- **P4/P9** — no `!=` loop sentinels; every poll loop has a `<` bound. Files
  without a literal `timeout`/`wait_until` rely on the project-wide
  `pytest-timeout` (600 s) and/or delegate to poll helpers that carry their own
  `timeout` parameter.
- **P10** — `test_srv6.py` waits on tshark's `Capturing on ...` stderr line
  AND on the pcap file growing past its header (per the P10 lesson), not on
  `p.poll() is None`.
- **P11** — `test_tc.py` probes iperf3 readiness passively via `ss -ltn`; no
  `nc -z` against the one-shot server. (`nc -z` remains only inside
  `check_tcp_connectivity`, whose server is a re-spawning plain `nc -l`.)
- **P12** — `test_exabgp.py` poll timeout 900 s with `@pytest.mark.timeout(1200)`.

## Ready-to-run audit block

```bash
cd ipmininet/tests
rg -n "time\.sleep\(\s*[0-9]" .            # P1
rg -n "\.wait\(\)|\.communicate\(\)" .      # P2 (then inspect)
rg -n "\[[^]]+\]\[" .                       # P3
rg -n "while t != " .                       # P4
rg -n '"/tmp/|server_port=' .               # P5
rg -n "sleep.*[Ww]ait" .                    # P6
rg -n "poll\(\) is None|isfile\(|getsize\(" .  # P10
rg -n "nc -z|:5201" .                       # P11
rg -n "timeout=[0-9]{3}" .                  # P12
rg -L "timeout|wait_until" .                # P9
```
