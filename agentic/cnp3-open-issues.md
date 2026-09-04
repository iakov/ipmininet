# cnp3/ipmininet open-issue triage (2026-09-04)

Fork-only knowledge doc. **Never push this to cnp3 or mimi-net upstream.** This
record exists so a future contributor can act on the upstream backlog without
re-reading 16 GitHub threads. Evidence base: issue bodies + comments fetched on
2026-09-04, checked against the mimi-net `master` checkout at `ca5cc37`.

Context anchors used to judge "likely fixed":
- OpenR daemon support removed upstream (`ac0627b` "remove EOL OpenR").
- Route-map / RIB-API redesign commits `2dcc603` / `72cefde`.
- Hub fix `08c8a21` ("linux bridge works as hub").
- FRR vtysh private mounts `7c18f45`; FRR 10.7.1 mgmtd migration `6497f55` (#36).
- Mininet install pinned to a fixed install.sh (`c3ba039a`, works around
  mininet/mininet#1120 pthread_yield/oflops); mininet dep is the `mimi-net`
  fork (`pyproject.toml`). ExaBGP 5.0.13 via pip (`3b55203`, #37).

Verdict legend: still-relevant / likely-fixed / needs-maintainer-input /
wontfix-likely.

## Entries

| # | Title (year) | Type | Verdict | Rationale |
|---|--------------|------|---------|-----------|
| 28 | Add proper dry_run for OpenR (2019) | feature-request | wontfix-likely | OpenR removed (`ac0627b`); generic per-daemon dry-run/config-check now lives in `router/__router.py`. |
| 73 | Add support for PBR daemon (2020) | feature-request | still-relevant | No `pbrd` module under `router/config/`; FRR PBR never implemented. Feature gap. |
| 99 | set_local_pref not flexible enough (2020) | feature-request | needs-maintainer-input | Route-map API redesign covered most; `set_local_pref` (`bgp.py`) gained a `name` param but still no `order`, unlike `filter`. Residual API gap; reporter's PR never landed. |
| 104 | HMAC TLV support? (2021) | usage/question | wontfix-likely | Maintainer answered "use commands in post_build()"; user thanked. Closable. |
| 107 | BGP filter pitfalls (2021) | bug-report | likely-fixed | Pitfalls superseded by route-map rewrite: `PrefixListEntry(action=DENY)` supported and rendered (`zebra.py`, `bgpd.mako`); entries sorted by auto order. Never confirmed by maintainer. |
| 108 | Add PCEP / PCEPLib support (2021) | feature-request | still-relevant | No `pathd`/PCEP module anywhere. Feature gap. |
| 116 | OpenR install broken on Ubuntu 20.04 (2021) | support-setup | wontfix-likely | OpenR installer deleted with the daemon (`ac0627b`). |
| 120 | Install fails on Ubuntu 22.04 (2022) | support-setup | likely-fixed | Root cause was mininet oflops `pthread_yield`; `install.py` now pins the fixed mininet install.sh + mimi-net fork; PEP-517 packaging handled. |
| 121 | OpenFlow switch possible? (2022) | usage/question | needs-maintainer-input | `IPOVSSwitch` (`ipovs_switch.py`) provides it; reporter was never pointed at it. |
| 122 | BGP RouteMapEntry call_action/exit_policy unusable (2022) | bug-report | likely-fixed | Crash was `bgpd.mako` referencing missing attrs; template now iterates `rm.entries[order]` and renders `call_action`/`exit_policy`; both fields exist on `RouteMapEntry` (`zebra.py:474`). Fix in `2dcc603`/`72cefde`. |
| 125 | Hub is not working (2023) | bug-report | likely-fixed | Issue's proposed fix is in master: `ipswitch.py` `brctl setageing 0` when hub (`08c8a21`). |
| 126 | Unbuffer stdin for node shell (2023) | usage/question, possible bug | needs-maintainer-input | Genuine hang report (exaBGP after link flaps) with full repro; no stdin handling in spawn path; maintainer stall. Unverified if reproducible on ExaBGP 5.x. Top real-bug candidate. |
| 127 | OpenR doesn't work (2023) | support-setup | wontfix-likely | PATH error for a removed daemon (`ac0627b`). |
| 128 | Hosts can't ping simple topology (2023) | usage/question | needs-maintainer-input | Reporter pinged before convergence; `BasicRouterConfig` runs OSPF+OSPF6. No code bug identified; no confirmation. |
| 129 | Modify FRR config / vtysh (2024) | usage/question | likely-fixed | Per-node vtysh via private `/var/run/frr` mounts (`7c18f45`); FRR 10.7.1 mgmtd applies per-node config in-node. |
| 130 | Router creation "configuration check reported an error" (2024) | support-setup | needs-maintainer-input | Matches dry-run config-check flow (`router/__router.py` pexec of daemon `dry_run`); likely FRR-version vs generated ospf6 config. Maintainer asked for config/FRR version; no reply. Possibly stale-docs/version compat, not verifiable. |

## Top candidates for maintainer action
1. #126 — only genuine behavioral hang report with repro; deserves re-test on current stack.
2. #130 — unresolved OSPF6D config-check failure; version-compat vs real bug unclear.
3. #99 — small residual API gap (`set_local_pref` lacks `order`).
4. #107 — superseded by route-map rewrite; confirm-and-close.
5. #73 / #108 — open feature gaps (pbrd, pathd/PCEP); likely wontfix unless championed.

## Likely fixed / closable without code
#28, #116, #127 (OpenR removed), #104, #120, #121, #122, #125, #128, #129.
