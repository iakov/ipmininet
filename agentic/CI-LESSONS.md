# CI / maintenance lessons (ipmininet)

Hard-won operational knowledge from the FRR/ExaBGP modernization (and the
earlier OpenR removal) plus CI work. Kept on the `me/agentic` branch (see
`AGENTS.md`), not merged to mimi-net/master.

## Repo topology (remotes)

- `cnp3/ipmininet`  = canonical upstream (read-only reference).
- `mimi-net/ipmininet` = fork where ALL real PRs are opened/merged (this is
  the "main" repo for our purposes). Local `master` tracks `mimi-net/master`.
- `iakov/ipmininet` = our fork, remote `origin`. PR heads are pushed here as
  `iakov:<branch>` and referenced that way in `gh pr create`.
- PRs must target `mimi-net` (not `cnp3`, not our fork).

## Merge workflow (safe defaults)

```bash
# after PR CI is green:
gh pr merge <N> -R mimi-net/ipmininet --squash --admin --delete-branch
# verify:
gh pr view <N> -R mimi-net/ipmininet --json state,mergeCommit
# sync local master + delete local & fork branches:
git checkout master && git fetch mimi-net master && git merge --ff-only mimi-net/master
git branch -D <branch>                        # local
git push origin --delete <branch>             # fork remote (gh --delete-branch may leave it)
```

- Squash-merges are the repo policy for multi-commit PRs. `--admin` bypasses
  branch-protection "stale base" blocks (e.g. Dependabot PRs).
- After merging one PR that touched workflows/files you will also edit, the
  other PR becomes stale: rebase it onto the new master via
  `gh api -X PUT repos/mimi-net/ipmininet/pulls/<N>/update-branch -f update_method=rebase`,
  then fetch that branch from `origin` (it is force-updated).
- Order matters: merge any workflow/version-bump PR (Dependabot) BEFORE
  opening a PR that edits the same workflow files, to keep bases clean.
- Master only changes via merged PRs. Never push directly to mimi-net master.

## CI architecture (why ~25 min runs)

Four workflows, all on `ubuntu-latest`:

| workflow | triggers | runs |
|---|---|---|
| `test.yaml` (Test IPMininet) | **pull_request only** (since #39) | `rootless` job: uv sync, ruff check/format, mdformat, check-duplicates, rootless unit tests. `test` job: full `install -a` + full suite with root. |
| `heavy-test.yaml` (Heavy test) | **master push + workflow_dispatch only** | Full `install -a` + full suite with `COVERAGE=1`, then coverage gate (85%, branch mode). This is the single bare-metal full-suite on master. |
| `container-test.yaml` (Container test) | pull_request + master push | Builds 2-stage Containerfile (`target: final`), then runs `scripts/ci-test.sh` in a privileged container. |
| `docs.yaml` (Build documentation) | PR + master push + dispatch | sphinx `-W` build. |

History: before #39 all three of test/heavy/container ran the same full
211-test suite on every master push (~75 min waste). Now master pushes run
heavy + container only. **Do not re-add a bare-metal master full-suite that
duplicates heavy-test.**

- `scripts/run-tests-parallel.sh`: xdist `--dist=loadscope`, each worker in
  its own namespace via `scripts/py-unshare.sh`. Module order matters and is
  hard-coded: `test_exabgp.py` first (9-min worst-case wait), then
  `test_srv6.py`, `test_tc.py`, ... A `-j N` flag or `XDIST_WORKERS` env
  overrides worker count (default = nproc). `COVERAGE=1` adds cov flags.
- Coverage gate: `pyproject.toml [tool.coverage.report] fail_under = 85`,
  `branch = true`. heavy-test is the enforcement point; coverage XML/HTML
  uploaded as artifact `coverage-full` and to Codecov (`slug` pinned to repo).
  Raised 84 → 85 in #41; #43 lifted the measured full-suite total to 88.38%
  (~3.4pp headroom, so re-raising the gate now has room). The heavy-test gate
  runs only on master push / dispatch, so a PR that changes
  coverage-sensitive code should be pre-validated by dispatching heavy-test
  on the fork branch before merging.
- Per-test timeout: `pyproject.toml [tool.pytest.ini_options] timeout = 600`
  (signal method). A single test that would wait longer gets killed at 600s.
- Container run entrypoint `scripts/ci-test.sh`: creates `/run/sshd` and
  starts OVS if needed, then delegates to `run-tests-parallel.sh` unless given
  explicit pytest args (for debug runs).
- `uv` is used everywhere (not pip); venv is cached via `uv.lock` hash;
  compiled FRR deps cached under `/home/runner/ci-deps` keyed on
  uv.lock/pyproject/install files + OS version.

## Resolved CI flake: test_srv6 `test_static_examples` (fixed #38)

Symptom: `test_srv6.py::test_static_examples[routesN-...]` used to fail with
"expected the path from h6 to h4 to go through ['r6','r5','r4'] but it went
through []" — the *same code* passes on other runners of the same commit, and
the failing parametrization varies per run (routes0/routes1/routes4 ...). It
only ever showed up under coverage (`COVERAGE=1`) / container load.

Root cause: the test asserted IPv4 connectivity
(`assert_connectivity(net, v6=False)`) and then immediately measured an
**IPv6** path. OSPFv6 had not converged yet under load, so `sr_path()` pings
lost packets → returned `[]` for all 30 near-instant retries (no sleep budget)
→ assertion fired. NOT an ExaBGP/FRR regression.

The fix (#38): a targeted wait for the exact measured endpoints before each
path assertion:
`_wait_v6_connectivity(net, src, dst_ip, timeout=120)` pings until 0% loss.

Critical lesson: **do NOT "fix" this by adding `assert_connectivity(net, v6=True)`**
— full v6 mesh never converges in that topology (hosts not on the measured
paths, e.g. h3, stay unreachable over v6). Tried that first; all 7
parametrizations then burned the 600 s timeout (25+ min per run, both
bare-metal and container). Wait only for the specific (src→dst) pairs the
assertions actually exercise.

Also in that test file: `sr_path()` requires `tshark` and `nmap`; it infers
paths from tshark pcaps, ordering captured packets per probe burst (pure
logic covered by `test_pure.py`). Keep that logic's invariants intact.

## ExaBGP 5.0.13 migration (#37)

- ExaBGP is installed **into the uv venv via pip** now (no apt/system install);
  see `install.py` `install_exabgp` and the `ExaBGPVersion = "5.0.13"` knob.
  The Containerfile and `scripts/ci-save-deps.sh`/`ci-restore-deps.sh` were
  updated so the venv-with-exabgp is cached/restored in CI.
- Real show-stopper found during the migration: ExaBGP 5.x only accepts
  Python-logging level names. `log.level = CRIT` (the 4.x syslog severity)
  makes 5.x abort at startup with `ValueError: invalid value for log.level :
  CRIT` → daemon never forms a session → routes never reach the FRR RIB → the
  9-minute test timeout fires. The default lives in
  `ipmininet/router/config/exabgp.py` `ExaBGPDaemon.set_defaults`
  (`level="CRITICAL"` now).
- ExaBGP 5.x startup line: `exabgp --env-file <env> server <cfg>`.
- Config dry-run/validate (fail-fast before daemon start) must be
  `exabgp --env-file <env> validate <cfg>` (the 4.x `--validate --env` syntax
  is gone); this is wired into the config object's `dry_run` property.
- `--env-file` is parsed before the subcommand in exabgp's main.py.
- Version probing: `exabgp version` / `exabgp --version`.

## FRR 10.7.1 + mgmtd (#36)

- FRRouting now uses mgmtd-based config management; daemons and cleanup
  patterns include `mgmtd` (`pkill -SIGINT -f "^mgmtd"`).
- `FRRoutingVersion = "10.7.1"` in install.py; frr is compiled under
  `/root/frr` (builder) and the compiled deps are cached in CI (`ci-deps`).
- `mininet` dependency must remain the `mimi-net/mininet` fork — a CI step
  greps `pyproject.toml` for it and fails otherwise.

## Dependabot / actions versions

- Dependabot (actions-dependencies group) opens bump PRs on mimi-net; they can
  sit BLOCKED on a stale base yet be perfectly green → merge with `--admin`.
- Current action majors in use: checkout@v7, setup-uv@v7, cache@v6,
  docker/setup-buildx@v4, docker/build-push-action@v7, upload-artifact@v7,
  codecov-action@v7 (upload-artifact/codecov bumped v4→v7 by #34).

## Useful commands

```bash
gh pr checks <N> -R mimi-net/ipmininet           # status table
gh run view <run> -R mimi-net/ipmininet          # job list
gh run view <run> -R mimi-net/ipmininet --log-failed   # failure lines
gh api repos/mimi-net/ipmininet/actions/jobs/<job>/logs | rg 'FAILED|passed in'
gh run rerun <run> -R mimi-net/ipmininet --failed      # rerun only failed
```

## Rerunning flaky jobs vs re-pushing

- Re-pushing to the PR branch supersedes/cancels in-progress runs for that PR
  (per-workflow `concurrency: cancel-in-progress`), so a fresh commit restarts
  CI cleanly.
- `gh run rerun <run> --failed` reruns only the failed job(s) of a completed
  run — good for confirming a flake vs a real regression. When you do this,
  the rerun job gets a *new* job id (checks table will show the new id).

## Misc pitfalls

- `assert_connectivity(net, v6=True)` = full host-pair v6 sweep, potentially
  huge/never-converging in non-mesh topologies. Prefer targeted endpoint waits.
- Don't trust a single passing run to clear a flaky test; look for the same
  commit passing on sibling runners before blaming the change.
- `pytest --timeout` default of 600 s makes "it hangs forever" look like a
  per-test timeout; correlate timestamps with which test was running.
- Coverage-instrumented runs are slower and expose timing flakes that the
  non-coverage bare-metal run won't. If a flake appears only in heavy-test,
  it is timing-sensitive by nature.

## Lint-debt final cleanup (PRs #45 + #46, commits 0188094 + 04e6f7d)

- PR #45 = real refactors (split `sr_path` in `tests/test_srv6.py`,
  `Named.build_reverse_zone`/`DNSZone.apply`, `IPNet.ping` via a new
  `_ping_addressing`). PR #46 = PLC0415 code fixes + inline noqa. Both merged
  green on the first CI pass.
- Safe split pattern used to clear PLC0415 without breaking imports: move the
  offending classes into a NEW leaf module (so it may import the daemon
  configs at module level) and re-export them unchanged from the package
  `__init__`. Before doing so, `rg` that nothing imports the classes from the
  old `.base` path directly — only the package path — then keep base lean.
- `ruff check .` by default flags unused noqa (RUF100): if it passes, every
  inline `# noqa` matches a live diagnostic — use it to validate the sweep
  after bulk-adding noqa comments.
- Inline-noqa placement rules learned while sweeping 47 sites:
  - The comment must be on the *diagnostic* line (the `raise`/`def` opening
    line for multi-line statements), not the closing paren.
  - Appending `# noqa` can push a line past 88 → E501. For single-line raises
    that overflow, rewrap to `raise X(  # noqa: TRY003` + message on its own
    line + `) [from None]` (ruff format accepts this form).
  - Combining rules on one tag, e.g. `# noqa: PLR0913, PLR0917`, keeps the
    diff small; keep the tag bare (no prose).
- Relying on ruff JSON output (`.venv/bin/ruff check . --output-format json`)
  makes bulk noqa insertion precise (file/row/code). Scratch scripts live in
  the git-ignored `.tmp/` (only `.tmp`, never `/tmp`).
