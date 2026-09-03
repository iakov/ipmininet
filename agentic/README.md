# agentic/ — knowledge & diagnostics for this repo

Durable agent/useful knowledge that must **not** go to upstream
(`mimi-net/ipmininet` or `cnp3`). Lives on the `me/agentic` branch. See the
root `AGENTS.md` for the standing rules that govern this branch.

## Contents

| File | What it holds |
| --- | --- |
| `CI-LESSONS.md` | Repo topology (remotes), safe merge workflow, CI architecture & run book |
| `NOTES.md` | Working notes: resolved flakes/fixes, deferred work, dependabot & hygiene status |
| `session-notes.md` | End-to-end session knowledge & plans (e.g. the fix/ci-clean delivery) |
| `FLAKY_REVIEW.md` | Flaky-test pattern catalog + audit guide (grep-able checklist) |

## Diagnostic tooling (NOT committed — in gitignored `.tmp/tools/`)

Flake repros and probes from the link-failure/DAD/OSPF/DNS debugging live in
`.tmp/tools/` (mirrored from `.tmp/` scratch, which is git-ignored):

- Repro/diagnostics: `repro_cycle.py`, `repro_linkfail.py`, `repro_dad.py`,
  `repro_dad_scale.py`
- Probes: `probe_addr.py`, `probe_cost.py`, `probe_fp2.py`, `probe_nocache.py`,
  `probe_v6.py`
- DNS / named tracing: `dns-diag.py`, `patch_named.py`, `sitecustomize.py`,
  `dns-capture.sh`, `trace-named.sh`
- Container verification: `container-dns-validate.sh`, `container-verify.sh`
- Misc: `gen_bgp.py`, `phase_ospf.py`

Rules: `.tmp/` never gets committed; `gh-token.txt` there is a credential and
must never be committed anywhere. Treat `.tmp/tools/` as scratch — anything
worth keeping long-term should be distilled into the docs above.
