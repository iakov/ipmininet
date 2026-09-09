# cnp3/ipmininet open-issue triage (2026-09-10, refreshed)

Fork-only knowledge doc. **Never push this to cnp3 or mimi-net upstream.** This
record exists so a future contributor can act on the upstream backlog without
re-reading 16 GitHub threads. Evidence base: issue bodies + comments, re-checked
against the mimi-net `master` checkout at `ccb14ed` (post #51).

Stack anchors used to judge "likely fixed":
- FRRouting 10.7.1 + mgmtd config (`6497f55`, #36); ExaBGP 5.0.13 via pip
  (`3b55203`, #37); Ubuntu 26.04 container (#32); Python >= 3.12.
- OpenR daemon support removed (`ac0627b`); hub fix `08c8a21`
  (brctl setageing 0); mininet install pinned (`c3ba039a`).
- Route-map redesign: ordered entries (`DEFAULT_POLICY`=65535 allow-all),
  `PrefixListEntry(action=...)`, `filter`/`deny`/`permit` expose `order`;
  bgpd.mako renders entries by order incl. `call_action`/`exit_policy`.
- 2026-09-10: BGP set-action ordering + latent crash fixed (PR mimi-net #51,
  merged `ccb14ed`, head `9284ab8`; rootless model test `test_bgp_model.py`).

Verdict legend: fixed-by-us / resolved-by-stack / still-relevant /
needs-maintainer-input / wontfix-likely.

## Entries

| # | Title (year) | Type | Verdict | Rationale |
|---|--------------|------|---------|-----------|
| 28 | Add proper dry_run for OpenR (2019) | feature-request | wontfix-likely | OpenR removed (`ac0627b`); generic per-daemon dry-run/config-check lives in `router/__router.py`. |
| 73 | Add support for PBR daemon (2020) | feature-request | still-relevant | No `pbrd` module; FRR PBR never implemented. Feature gap; not on roadmap. |
| 99 | set_local_pref not flexible enough (2020) | feature-request + bug | **fixed-by-us** | `set_local_pref`/`set_med`/`set_community` now take `order` (parity with deny/permit/filter). Also uncovered+fixed a real crash: two set actions on the same peer with different match conditions hit `AttributeError: 'NoneType' object has no attribute 'entry'` in `add_set_action` (lookup-miss deref of None). PR mimi-net #51 (`ccb14ed`). Default (order=None) unchanged -> configs byte-identical. |
| 104 | HMAC TLV support? (2021) | usage/question | wontfix-likely | Maintainer answered "use commands in post_build()"; still the answer. |
| 107 | BGP filter pitfalls (2021) | bug-report | resolved-by-stack | Superseded by route-map rewrite (explicit DENY, ordered entries, allow-all default at DEFAULT_POLICY). Never confirmed by maintainer; ask to re-test. |
| 108 | Add PCEP / PCEPLib (2021) | feature-request | still-relevant | No `pathd`/PCEP module. Feature gap; not on roadmap. |
| 116 | OpenR install broken on Ubuntu 20.04 (2021) | support-setup | wontfix-likely | OpenR installer deleted with the daemon (`ac0627b`). |
| 120 | Install fails on Ubuntu 22.04 (2022) | support-setup | resolved-by-stack | Root cause mininet oflops `pthread_yield`; install.py pins fixed mininet install.sh + mimi-net fork; PEP-517/668 handled. |
| 121 | OpenFlow switch possible? (2022) | usage/question | resolved-by-stack | `IPOVSSwitch` provides it, documented in `docs/switches.rst`; reporter never pointed at it. |
| 122 | BGP RouteMapEntry call_action/exit_policy unusable (2022) | bug-report | resolved-by-stack | Crash was bgpd.mako; template now iterates `rm.entries[order]` and renders `call_action`/`exit_policy`. Ask to re-test. |
| 125 | Hub is not working (2023) | bug-report | resolved-by-stack | Issue's proposed fix is in master (`brctl setageing 0` when hub). |
| 126 | Unbuffer stdin for node shell (2023) | usage/question, possible bug | needs-maintainer-input | No custom stdin in the spawn path (`router/__router.py` Node.popen); "hang after N flaps" consistent with a consumer-pipe deadlock (reporter's own xterm experiment never hangs). Not reproduced at reduced scale on ExaBGP 5.0.13. Full-scale repro (~60 routers, ~16 min flaps) not cost-effective; keep open, invite minimal repro. |
| 127 | OpenR doesn't work (2023) | support-setup | wontfix-likely | PATH error for a removed daemon. |
| 128 | Hosts can't ping simple topology (2023) | usage/question | resolved-by-stack | Reporter pinged before IGP convergence (default config runs OSPF+OSPF6); use poll pattern. No code bug identified. |
| 129 | Modify FRR config / vtysh (2024) | usage/question | resolved-by-stack | Per-node vtysh via private `/var/run/frr` mounts (`base.py:78`); FRR 10.7.1 mgmtd applies per-node config in-node. |
| 130 | Router creation "configuration check reported an error" (2024) | support-setup | resolved-by-stack | Ubuntu 18.04/old apt-FRR vs generated config; on FRR 10.7.1 every OSPF6 topology starts cleanly (config-check runs at each router start; full suite green). 18.04 below py>=3.12 floor. Invite retest on a supported image. |

## Top candidates for maintainer action (post-2026-09-10)
1. #99 — DONE: PR mimi-net #51 merged (`ccb14ed`). Draft comment for cnp3 #99 ready (see below).
2. #130 — draft comment invites retest on current image; keep open.
3. #126 — keep open; draft comment asks for a minimal repro on ExaBGP 5.
4. #73 / #108 — open feature gaps; contributions welcome, no roadmap slot.
5. Remaining "resolved-by-stack" (#107/#121/#122/#125/#128/#129/#120, #104)
   and "OpenR removed" (#28/#116/#127) — draft comments prepared; nothing closed.

## Comment drafts (2026-09-10)
Full polished 3-4 sentence drafts for all 16 issues, plus the analysis and a
commenting plan for review, live in the gitignored scratch dir
`.tmp/cnp3/` (`analysis.md`, `replies.md`, `commenting-plan.md`). Those files
are NOT committed (`.tmp/` is scratch); if they are lost, this table is the
durable summary and drafts can be regenerated from it. Nothing has been posted
to cnp3 and nothing will be without an explicit user prompt.
