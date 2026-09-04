# IPMininet notes

Working notes kept on the `me/agentic` branch (see `AGENTS.md`). The `.tmp/`
scratch dir is git-ignored; diagnostic scripts referenced here live in
`.tmp/tools/` (see `agentic/README.md`).

## Resolved: `test_randomFailure[3]` flake

- **Root cause**: `IPIntf.up(restore=True)` went through `setIP()`, which
  removes and re-adds every address on the interface. This kernel drops IPv6
  addresses on a link flap while IPv4 survives, so the saved set always differs
  and every restore churned addresses (brief `0.0.0.0` window). That races
  zebra/ospfd (`Failed to enqueue dataplane install`), and an OSPF route add can
  get stuck missing -> r1's routing table stays empty -> the assertion timed out.
- **Fix**: `ipmininet/link.py` `up(restore=True)` now restores only the missing
  addresses (the IPv6 the kernel dropped) and refreshes the cache afterwards.
  Commit `4ee10a9` (PR #18).
- **Validation**: 100-cycle down/restore stress clean (0 our-initiated
  `RTM_DELADDR`; was ~12/cycle before), linkfailure suite green 6x8 via xdist,
  ospf/iptables/ripng green, CI green on PR #18/#17 and post-merge master
  (run `33295807338` test job = 187 passed, 7 skipped).

## Resolved: docs build with uv (PR #23, merge `c8691c4`)

- mako 1.1.6 -> 1.4.1; docs migrated from m2r/recommonmark/mistune<2 to
  **sphinx-mdinclude** (+ `mistune>=3,<4`); added `sphinx.ext.napoleon`
  (standalone napoleon 0.7 broken on Py3.12); `language='en'`.
- Deleted `docs/requirements.txt`; docs now a uv **dependency group**
  (`[dependency-groups] docs` in `pyproject.toml`; uv.lock regenerated) — uv is
  the SSOT for all Python deps (runtime, dev, docs).
- Added `.github/workflows/docs.yaml`: PR/push/workflow_dispatch; `uv sync
  --group docs`; `sphinx-build -b html -W docs docs/_build/html`; uploads
  `docs/_build/html` as `ipmininet-docs`. No tag/release work (per user).
- `-W`-clean fixes: removed `html_static_path=['_static']` (doesn't exist);
  `suppress_warnings=['autosectionlabel.*']` (api/*.rst duplicates;
  `autosectionlabel_prefix_document` broke README.md anchors so it was
  reverted); malformed docstrings fixed in `cli.py` `IPCLI.do_link`,
  `ipovs_switch.py` `IPOVSSwitch`/`__init__` (was inheriting mininet's broken
  `OVSSwitch.__init__` docstring), `iptopo.py` `addRouter` (`"param` typo),
  `zebra.py` `ZebraList.__init__` field list. `contribute.rst` updated.
- Validated: container `sphinx-build -W` exit 0; `test_cli` 13 pass;
  `test_pure` 19 pass; docs CI job green.

## Resolved: `test_iptables` IPv4 ping (PR #40, merge `2e518a4`)

- Found by the latent P1–P12 FLAKY_REVIEW sweep (2026-09-04, see
  `agentic/FLAKY_REVIEW.md` "Last audit"): the IPv4 "should NOT be blocked"
  check did a **single-shot** `ping -c 1` right after `net.start()`, while the
  sibling IPv6 "should be blocked" check already polled via `wait_until`.
- A first packet can drop under load even when traffic is not blocked, so the
  assert could flake (P2). Fixed by wrapping the ping in
  `wait_until(_ipv4_ping_ok, timeout=30, interval=0.5)` — same shape as the
  IPv6 check below it.

## Follow-up items (all resolved as of 2026-09-04; kept for the record)

### pcre3 -> pcre2 (RESOLVED via #32 and #36)
- **Original state**: `install_libyang()` built libyang `v1.0.215` (pinned,
  build-dep of FRR 7.5) which needs PCRE1; `install.py`/`Containerfile`
  installed `libpcre3-dev`/`pcre-devel`. Ubuntu 26.04 dropped PCRE1 packages.
- **Why PCRE2 couldn't be a drop-in**: verified EVERY libyang v1.x tag
  (v1.0.215..v1.0.253) requires PCRE; PCRE2 only exists in libyang v2+ (FRR
  8+), which implied an FRR 7.5 -> 8.x + libyang upgrade.
- **What happened instead**:
  - #32 built **PCRE1 from source** (8.45, SHA-256-pinned) on Ubuntu 26.04
    when apt no longer ships it — a stopgap for the container.
  - #36 then migrated FRR to **10.7.1** + **libyang v3** (`LibyangVersion =
    v3.13.6`) and **dropped the PCRE1 source build entirely**; libyang v3
    needs **PCRE2**, so `install.py` now installs
    `pcre2-devel`/`libpcre2-dev` and `Containerfile` ships `libpcre2-8-0`.

### ExaBGP (RESOLVED in stages: #22 4.2.25 -> #37 5.0.13 via pip)
- 4 tests were skipped (`test_exabgp.py`, `require_exabgp`) because exabgp
  could not run on Python 3.12.
- Root cause: exabgp 4.2.11 (the then-pinned `install.py` version) ships a
  **vendored `six.py` v1.10** (2015) whose meta-path importer only implements
  PEP 302 `find_module` — removed in Python 3.12 (PEP 451 `find_spec` is
  required). So `from exabgp.vendoring.six.moves import configparser` fails
  even though the `six.moves` attribute exists. The git tag, the PyPI sdist,
  and the zipapp all had six 1.10 — **the zipapp was NOT the trigger** (a
  pip/uv filesystem install of 4.2.11 fails identically).
- Upstream fixed it on the `4.2` branch (commit `3f867af33` "update six",
  v4.2.21+; also py3.12/3.13 docopt/asyncore fixes). Latest 4.2.x = **4.2.25**
  (git tag + PyPI), whose vendored six is 1.16 with `find_spec`.
- #22 (historical): bumped `ExaBGPVersion` 4.2.11 -> 4.2.25 (zipapp build),
  switched a broken-symlink check to `os.path.lexists`, fixed `check_as_path`
  string-vs-int comparison in `test_exabgp.py`, updated skip reasons. Validated
  in dev container (zipapp 4.2.25, daemon starts, all 4 tests pass). This is
  now **superseded** by #37.
- #37 (current): ExaBGP migrated to **5.0.13 installed into the uv venv via
  pip** (no apt/system install). See `agentic/CI-LESSONS.md` "ExaBGP 5.0.13
  migration (#37)" for the full story, including the show-stopper that 5.x
  only accepts Python-logging level names (`log.level = CRIT` aborts startup).
- Misc: `pkill -f "^exabgp"` is the daemon kill pattern.

### OpenR (REMOVED — PR #35, commit `ac0627b`)
- Open/R = Meta's open-source routing daemon (open-sourced ~2016), effectively
  unmaintained since ~2019. It was part of the ORIGINAL ipmininet (present in
  cnp3 upstream, added via upstream PR #9 IgorFilimonov) — not a local addition.
- Was never tested in CI because `install -a` did not build it (needs ~4GB RAM,
  slow 2019 build); 3 tests skipped with reason "OpenR daemon not available".
- **Removed** as EOL: PR #35 ("refactor: modernize installer and drop EOL
  OpenR", commit `ac0627b`) deleted the daemon support, its skip tests and the
  2019 build script; there are no `openr` references left on master.

### Lint / "reformatting PR" (MERGED as PR #25)
- ruff 0.16.5 default (5-category "recommended") set was **906 errors**;
  curated `select` in `pyproject.toml` (target-version py312). `--isolated`
  confirmed the default is ruff's built-in set (not a repo config).
- **Phase 1** (merged): infra (`[tool.ruff]`, `[tool.mdformat]`, dev group
  `ruff`/`mdformat`/`pre-commit`, pre-commit auto-fix + pre-push strict, CI
  lint step in `rootless` job, deleted `pylintrc`) -> auto-fix (safe+unsafe) +
  `ruff format` + `mdformat` -> 116 manual fixes. UP031: **all 32 printf
  strings converted to f-strings, zero impossible**. BLE001 partially fixed
  (ConfigDict->AttributeError); the intentional broad mako-render catch in
  `router/config/base.py` is unfixable -> BLE removed from curated `select`.
- **Phase 2** (merged): enabled E501/TRY003/PLR2004/PLR0913/PLR0917/
  PLC0415/PLR0912/PLR0911/PLR0915. Reflowed **45** E501 lines (f-strings,
  comments, docstring prose); per-file-ignored 23 genuinely-unbreakable
  (ASCII-art `simple_ospf_network.py`, shell cmd strings `install.py`, `ip
  addr` fixture `test_pure.py`). The 8 architectural rules cannot be
  implemented this time (TRY003 needs per-message exception classes, PLR2004
  needs named constants, PLR0913/0917/0912/0911/0915 need function refactors,
  PLC0415 is intentional circular-import avoidance) -> per-file-ignored for
  all existing files, so they stay selected for NEW files.
- `.git-blame-ignore-revs` was added (`c7fc045`, auto-fix hash) and then
  pointed at the *merged* auto-fix hash in `0ee53cb` (PR #27).
- pre-commit not run locally (needs network); config validated by reading.
- **PLR2004 now enforced with zero per-file-ignores** (PRs #41 + #42):
  PR #41 introduced `IP_V4`/`IP_V6` in `ipmininet/utils.py` and named the
  product `version == 4/6` comparisons plus the legacy `LinkDescription`
  0/1/3 indexes; PR #42 named the last test/example magic constants
  (`MIN_RESERVED_TABLE`, `MAX_PREFIXES_PER_AFI`, prefix-length, probe-window
  and convergence constants) and deleted every remaining `PLR2004`
  per-file-ignore. Any new magic constant used in a comparison now fails
  `ruff check .` in CI/pre-commit. Scope caveat: PLR2004 only covers
  *comparisons*; indexes/defaults/assignments are out of linter scope.
- **TRY003 partially paid down** (PR #44, commit `1ac7cc9`): for the seven
  files whose *only* per-file-ignore was TRY003, each raise message was moved
  into a dedicated exception class subclassing the previously-raised builtin
  (`topologydb.py`: NoSuchNodeError/NoSuchLinkError/NotARouterError;
  `router/config/iptables.py`: UnknownTable/Chain/DefaultPolicy/
  RuleParameterError; `router/config/exabgp.py`: NotHexRepresentableError,
  UnknownBGPAttributeError; `node_description.py`: LinkIndexError,
  NodeNotOnLinkError; `iptopo.py`: UnknownTopologyAttributeError;
  `overlay.py`: NoCaptureAnchorError; `tests/test_radv.py`: uses
  `pytest.fail`). Result: TRY003 count 46 -> **32**, seven ignore entries
  dropped. The 32 remaining TRY003 live in files that also carry
  PLR091x/PLC0415 ignores (ipnet, srv6, zebra, bgp, base, utils,
  install/utils, tests/utils) and stay deferred as a group.

### ExaBGP CI flake (fixed — PR #24, branch `fix/exabgp-rib-timing-flake`)
- Symptom: `test` job of run 33305086380 failed `test_example_exabgp
  [topo_test0-as2]` with `KeyError: '8.8.8.0/24'` (1 failed, 190 passed).
  Rootless/container-test/docs/heavy-test all passed; only root `test` failed.
- Root cause: test slept a **fixed 130s** then checked the RIB. ExaBGP runs
  `passive=True` + `tcp.delay=2` (waits up to 2 min before sending UPDATEs);
  under parallel xdist load, session establishment + route delay can exceed
  130s -> routes not yet in RIB. Timing flake, not a product bug.
- Fix: `wait_for_expected_routes()` polls the RIB every 5s (default timeout
  introduced at 300 in #24, raised to 540 in the anti-flaky PR #26, then
  hardened to **900** in #27/`0ee53cb`) and returns as soon as all expected
  routes appear; `get_rib_routes()` factored out for the wait + validation;
  fixed `check_correct_rib` assert-order bug (indexed before membership assert
  -> bare KeyError instead of the message).

### CI Node-20 deprecation
- `actions/cache@v4`, `actions/checkout@v4`, `astral-sh/setup-uv@v5` forced to
  Node 24. Resolved by dependabot: #20 (actions-dependencies group) and later
  #34 (upload-artifact/codecov v4->v7); current majors are in `CI-LESSONS.md`.

## Dependabot
- Config `.github/dependabot.yml` committed (PR #11) but the bot was not
  enabled; owner fixed it. Groups: python-dependencies / actions-dependencies /
  docker-dependencies, monthly.
- Status (2026-09-04): **no open PRs**. #19 docker ubuntu 24.04->26.04 was
  **closed** (superseded by the manual container bump in #32); #20 actions (5
  updates) **merged** (`db358a1`); #21 python **auto-closed** when #23 merged
  the mako/mistune updates; #34 actions-dependencies (2 updates) **merged**
  (`030c659`).

## Repo / local hygiene
- Fork `master` resynced to `mimi-net/master` through `1ac7cc9` (PRs #43 +
  #44; ff + pushed). Upstream released **v1.2.7** (2026-08-31).
- Coverage gate raised 84 → **85** (PR #41, commit `13c01c0`); then PR #43
  (commit `c308745`) added rootless unit tests for the three ~0% modules and
  pushed the measured full-suite total from ~85.7% to **88.38%** (TOTAL 3745
  stmts, 368 missed -> ~3.4pp headroom over the gate). dnsmasq/dhcprelay now
  100%; `ipovs_switch.py` ~47%. Gate enforced only by heavy-test (rootless PR
  job uses `--cov-fail-under=0`). Lesson: the heavy-test coverage gate only
  counts modules imported during the *explicit file list* in
  `scripts/run-tests-parallel.sh`, so new test files MUST be appended to that
  list (and, if rootless-safe, to the 4-file list in `.github/workflows/
  test.yaml`). Lesson 2: `tmp_path`-using tests must not land as the last
  module on an xdist worker (basetemp race) — prefer `tempfile.mkdtemp`; and
  beware substring asserts (`"stp_enable=true" in "rstp_enable=true"`).
- Deleted merged fork branches (local + remote): `fix/link-restore-no-address-churn`,
  `ci/run-capture-tests`, `feat/network-capture-readiness`, `ci/fix-container-image`,
  `deps/mako-bump-and-sphinx-mdinclude`, `chore/ubuntu-2604` (#32),
  `ci/codecov-slug` (#33), `fix/iptables-ipv4-poll-wait` (#40),
  `chore/coverage-85-lint-cleanup` (#41), `chore/no-magic-values` (#42),
  `chore/uncovered-daemon-tests` (#43), `chore/try003-exceptions` (#44).
  NOTE: `gh pr merge --delete-branch` does NOT delete the fork head branch
  (head repo is `iakov`); the manual `git push origin --delete` is required.
- Pruned stale `mimi-net/dependabot/uv/python-dependencies-*` and
  `mimi-net/dependabot/docker/docker-dependencies-*` tracking refs.
- Deleted stale local `hotfix-ci`. Kept `cnp3` remote (original upstream ref).
- `origin` now holds only `master` + `me/agentic` (knowledge branch).
- New upstream knowledge doc: `agentic/cnp3-open-issues.md` (triage of the 16
  open cnp3 issues; fork-only, never push upstream).

## Podman-machine lesson (CPU waste)
- 4 orphaned `yes` load-generators (root, from flake-repro CPU saturation,
  `docker exec -d ... yes > /dev/null &`) were left running ~74% CPU each for a
  day. Killed via `docker exec dev-installed pkill -9 -x yes` (now harmless
  zombies under `sleep infinity` PID 1). REMEMBER to kill load generators.
- Podman machine `ipmininet` (qemu VM, 4 CPU/4GiB) was left running ~55% CPU +
  1.2GB RAM. Stopped: `podman machine stop ipmininet` (not removed; disk kept).
- Podman Desktop GUI (~24% CPU idle) left open by user.

## Flake-repro / diagnostic tooling (kept in gitignored `.tmp/tools/`)
- `repro_cycle.py` (down/restore stress, counts zebra DELADDR / failed-installs,
  saves daemon logs before teardown), `repro_linkfail.py`, `probe_*.py`.
- Dev container `dev-installed`: bind-mounts the repo to `/workspace`, venv
  `/opt/venv` (ipmininet editable), real mimidump at `/usr/local/bin/mimidump`,
  image `ipmininet-dev:mimidump`. `DOCKER_HOST=unix:///var/run/docker.sock`
  (podman rootless socket broken). FRR 10.7.1 daemon logs at
  `/tmp/{zebra,ospfd}_rN.log`; xdist workers isolated via `scripts/py-unshare.sh`
  (fresh tmpfs /tmp + private netns).
