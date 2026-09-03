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
  Commit `3ba67f0` (PR #18).
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

## Deferred / future work

### pcre3 -> pcre2 (deferred, scoped PR later)
- **Where used**:
  - `ipmininet/install/install.py:121` `libpcre3-dev` (Debian/Ubuntu),
    `:123` `pcre-devel` (Fedora) — in `install_libyang()`.
  - `Containerfile:21` `libpcre3-dev` (dev-container build deps).
  - `ipmininet/install/build_openr-rc-20190419-11514.sh:6` (OpenR 2019 build;
    not run by `-a`).
- **Why**: `install_libyang()` builds libyang `v1.0.215` (pinned, build-dep of
  FRR 7.5) for YANG/XPath regex; libyang v1 CMakeLists has
  `find_package(PCRE REQUIRED)`.
- **Migration**: verified EVERY libyang v1.x tag (v1.0.215..v1.0.253) requires
  PCRE; PCRE2 only in libyang v2 (FRR 8+). So pcre2 needs FRR 7.5 -> 8.x +
  libyang v1 -> v2 upgrade (config template + daemon-behavior risk). Scoped PR
  later; do not attempt casually.

### ExaBGP (DONE — fixed in this work, see the PR)
- 4 tests were skipped (`test_exabgp.py`, `require_exabgp`) because exabgp
  could not run on Python 3.12.
- Root cause: exabgp 4.2.11 (the pinned `install.py:13` version) ships a
  **vendored `six.py` v1.10** (2015) whose meta-path importer only implements
  PEP 302 `find_module` — removed in Python 3.12 (PEP 451 `find_spec` is
  required). So `from exabgp.vendoring.six.moves import configparser` fails
  even though the `six.moves` attribute exists. The git tag, the PyPI sdist,
  and the zipapp all had six 1.10 — **the zipapp was NOT the trigger** (earlier
  note said pip/uv fixes it: FALSE; a pip/uv filesystem install of 4.2.11 fails
  identically).
- Upstream fixed it on the `4.2` branch (commit `3f867af33` "update six",
  v4.2.21+; also py3.12/3.13 docopt/asyncore fixes). Latest 4.2.x = **4.2.25**
  (git tag + PyPI), whose vendored six is 1.16 with `find_spec`.
- Fix implemented (kept zipapp architecture per user):
  - `install.py`: `ExaBGPVersion` 4.2.11 -> 4.2.25.
  - `install.py`: `os.path.exists(final_link)` -> `os.path.lexists(...)` so a
    stale **broken** symlink is removed before re-symlinking (pre-existing
    re-install bug exposed during validation).
  - `test_exabgp.py`: `check_as_path` parses FRR JSON AS-PATH strings to ints
    (`as_rib = [int(asn) for asn in as_path_rib.split(" ")]`) — latent bug
    (string vs int compare) that only surfaced once tests actually ran.
  - `tests/__init__.py`: updated skip reason + docstring.
- Validated in dev container: `install_exabgp()` from source builds tag 4.2.25
  zipapp, `/usr/sbin/exabgp --version` -> 4.2.25 rc=0, daemon starts; all 4
  `test_exabgp.py` cases **pass** (routes verified in FRR BGP RIB). FRR JSON
  types confirmed: `path` is a string, `origin` uppercase string, `metric` int.
- Misc: `pkill -f "^exabgp"` is the daemon kill pattern; `uv pip install` of
  `exabgp==4.2.11` pulls in `setuptools` as a build dep.

### OpenR
- Open/R = Meta's open-source routing daemon (open-sourced ~2016), effectively
  unmaintained since ~2019. It is part of the ORIGINAL ipmininet (present in
  cnp3 upstream, added via upstream PR #9 IgorFilimonov) — not a local addition.
- Not tested because `install -a` does not build it (`-f/--install-openr`;
  help text: slow build, needs ~4GB RAM). 3 tests skip with reason "OpenR daemon
  not available (needs build, not run in CI)".
- Candidate for removal as obsolete (unmaintained daemon, heavy 2019 build).
  Keep the skip for now; possible future removal PR.

### Lint / "reformatting PR" (DONE on branch `chore/lint-format-ci`)
- ruff 0.16.5 default (5-category "recommended") set = **906 errors**; curated
  `select` in `pyproject.toml` (target-version py312). `--isolated` confirmed
  the default is ruff's built-in set (not a repo config).
- **Phase 1** (8 commits, lint/format/tests green): infra (`[tool.ruff]`,
  `[tool.mdformat]`, dev group `ruff`/`mdformat`/`pre-commit`, pre-commit
  auto-fix + pre-push strict, CI lint step in `rootless` job, deleted
  `pylintrc`) -> auto-fix (safe+unsafe) + `ruff format` + `mdformat` -> 116
  manual fixes. UP031: **all 32 printf strings converted to f-strings, zero
  impossible**. BLE001 partially fixed (ConfigDict->AttributeError); the
  intentional broad mako-render catch in `router/config/base.py` is
  unfixable -> BLE removed from curated `select`.
- **Phase 2** (1 commit): enabled E501/TRY003/PLR2004/PLR0913/PLR0917/
  PLC0415/PLR0912/PLR0911/PLR0915. Reflowed **45** E501 lines (f-strings,
  comments, docstring prose); per-file-ignored 23 genuinely-unbreakable
  (ASCII-art `simple_ospf_network.py`, shell cmd strings `install.py`, `ip
  addr` fixture `test_pure.py`). The 8 architectural rules cannot be
  implemented this time (TRY003 needs per-message exception classes, PLR2004
  needs named constants, PLR0913/0917/0912/0911/0915 need function refactors,
  PLC0415 is intentional circular-import avoidance) -> per-file-ignored for
  all existing files, so they stay selected for NEW files. Verified: 0 errors,
  format/mdformat clean, test_pure 19 / test_cli 13 / test_misc 42 / test_link
  13 pass.
- `.git-blame-ignore-revs` deliberately NOT added (user deferred).
- pre-commit not run locally (needs network); config validated by reading.

### ExaBGP CI flake (fixed — PR #24, branch `fix/exabgp-rib-timing-flake`)
- Symptom: `test` job of run 33305086380 failed `test_example_exabgp
  [topo_test0-as2]` with `KeyError: '8.8.8.0/24'` (1 failed, 190 passed).
  Rootless/container-test/docs/heavy-test all passed; only root `test` failed.
- Root cause: test slept a **fixed 130s** then checked the RIB. ExaBGP runs
  `passive=True` + `tcp.delay=2` (waits up to 2 min before sending UPDATEs);
  under parallel xdist load, session establishment + route delay can exceed
  130s -> routes not yet in RIB. Timing flake, not a product bug.
- Fix: `wait_for_expected_routes()` polls the RIB every 5s up to 300s and
  returns as soon as all expected routes appear; `get_rib_routes()` factored
  out for the wait + validation; fixed `check_correct_rib` assert-order bug
  (indexed before membership assert -> bare KeyError instead of the message).
- PR #24 opened against mimi-net, to be merged BEFORE the formatting PR.

### CI Node-20 deprecation
- `actions/cache@v4`, `actions/checkout@v4`, `astral-sh/setup-uv@v5` forced to
  Node 24. Now handled by dependabot (PR #20, actions-dependencies group).

## Dependabot
- Config `.github/dependabot.yml` committed (PR #11) but the bot was not
  enabled; owner fixed it. Groups: python-dependencies / actions-dependencies /
  docker-dependencies, monthly.
- Status (2026-08-30): #19 ubuntu 24.04->26.04 **open**; #20 actions (5
  updates) **merged** (`db358a1`); #21 python **auto-closed** when PR #23 merged
  the mako/mistune updates.

## Repo / local hygiene
- Fork `master` resynced to `mimi-net/master`:
  - `9e10a89` (earlier),
  - `c8691c4` (after PR #23 docs/uv work; ff + pushed, branch deleted).
- Deleted merged fork branches (local + remote): `fix/link-restore-no-address-churn`,
  `ci/run-capture-tests`, `feat/network-capture-readiness`, `ci/fix-container-image`,
  `deps/mako-bump-and-sphinx-mdinclude`.
- Pruned stale `mimi-net/dependabot/uv/python-dependencies-*` tracking ref.
- Deleted stale local `hotfix-ci`. Kept `cnp3` remote (original upstream ref).

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
  (podman rootless socket broken). FRR 7.5 daemon logs at
  `/tmp/{zebra,ospfd}_rN.log`; xdist workers isolated via `scripts/py-unshare.sh`
  (fresh tmpfs /tmp + private netns).
