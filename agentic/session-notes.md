# ipmininet — Session Knowledge & Plan (2026-08-25)

## Objective
Deliver PR #11 to upstream `mimi-net/ipmininet` (base `75290b9`, branch `fix/ci-clean`)
as a small, reviewable PR that **fixes pre-existing test failures** and **adds rootless
testing**, with a **minimal uv migration** and a **three-tier CI**. Tag `1.2.6` upstream
after merge. Create GitHub issues for non-fixable problems after CI is green.

## Current PR state (head `ccdefd8`)
5 commits on top of `75290b9` (mimi-net/master):
1. `dca6175` `fix(tests): address pre-existing test failures`
   - test_link: Python 3.12 reclassifies `2002::/16` (6to4) as private → global `2001::/16` sorts first
   - test_network_capture: skip (mimidump not shipped)
   - test_exabgp: real bug fix `asn_received == asn_expected` + skip (broken vendored six); NO f-string rewrites
   - test_openr: skip ×3 (OpenR build required)
   - install/__main__.py: `os.makedirs("/run/sshd", exist_ok=True)`; `-a` now installs mininet (`if args.all or args.install_mininet: install_mininet(output_dir, pip_install=not args.all)`)
   - install/install.py: `openvswitch-switch` on Ubuntu/Debian; **minimal mnexec path** under `-a` (`make mnexec` + cp to /usr/local/bin) to avoid `install.sh -a` which fails on Ubuntu 24.04 (`pep8` removed); **enable_ipv6 guard** — skip grub config if `/etc/default/grub` absent (container case)
   - install/utils.py: `pkg_resources` → `packaging.version.parse` (pkg_resources removed in setuptools 84)
2. `629c5d5` `test: add rootless local test runner and pure unit tests`
   - scripts/run-tests-local.sh (runs suite as non-root; root tests auto-skip via require_root marker)
   - ipmininet/tests/test_pure.py (19 rootless tests: `_parse_addresses`, `is_subnet_of`, `is_container`, `get_set`, `ConfigDict`, `ip_statement`)
   - test_misc.py: `test_ip_address_format` marked `@require_root` (calls `ip link set dev lo up`)
3. `53df86b` `build: migrate to uv (minimal)`
   - pyproject: `requires = ["setuptools>=61.2"]` (drop pytest-runner), add `requires-python = ">=3.12"` — base style kept
   - .python-version (3.12), uv.lock (generated, ~180 lines), .gitignore (+`.venv/`, `/.tmp/`, `.coverage`)
   - NO install.py refactor, NO ruff/pytest config, NO dev extra
4. `3e5197f` `ci: add containerized, rootless and heavy test workflows`
   - .github/workflows/test.yaml: `rootless` job (uv sync + run pure tests as non-root) + `test` job (install -a then full suite, `--ignore=test_exabgp.py --ignore=test_openr.py`)
   - .github/workflows/container-test.yaml: build Containerfile (gha cache) → `docker run --privileged` → `scripts/ci-test.sh test_misc.py test_pure.py`
   - .github/workflows/heavy-test.yaml: full suite on master + workflow_dispatch
   - Containerfile: single-stage ubuntu:24.04, `ENV UV_PROJECT_ENVIRONMENT=/opt/venv`, `PIP_BREAK_SYSTEM_PACKAGES=1`, `uv sync --all-extras`, `scripts/ci-install.sh`
   - scripts/ci-install.sh, scripts/ci-test.sh (set PIP_BREAK_SYSTEM_PACKAGES=1; OVS daemon bootstrap in ci-test.sh)
   - NO lint steps, NO coverage (deferred)
5. `ccdefd8` `chore: add dependabot config`
   - .github/dependabot.yml: uv + github-actions + docker ecosystems, monthly, grouped

## CI status on `ccdefd8`
- Container test: **SUCCESS** ✅ (container build + test_misc/test_pure subset)
- Test IPMininet: `rootless` job SUCCESS ✅; `test` (rootful) job: install step SUCCESS, **full test suite still in_progress** at time of saving
- Earlier failures on older SHAs were all fixed: YAML `run:` line-continuation folding (needed `run: |`), pkg_resources, pep8/mininet full install, grub missing.

## Root causes discovered (important knowledge)
- **YAML multi-line run**: GitHub Actions folds `run:` into single line unless `run: |` literal block. Backslash line-continuations fail.
- **setuptools 84** removed `pkg_resources`; base install.py imports it → use `packaging.version.parse` (packaging is a transitive dep).
- **mininet `install.sh -a`** fails on Ubuntu 24.04 (`Package 'pep8' has no installation candidate`). Minimal path: `make mnexec` + copy to `/usr/local/bin`; Python package comes from uv (pyproject dep), OVS from `openvswitch-switch` apt pkg.
- **enable_ipv6()** opens `/etc/default/grub` — absent in containers → guard `if not os.path.exists(grub_cfg): return` (do NOT pre-create the file; `update-grub` may be missing).
- **`-a` in base did NOT install mininet** (only `-m` did). Refactored code used `if args.all or args.install_mininet:` — reproduced.
- require_root marker: `pytest.mark.skipif(os.getuid() != 0, ...)` in ipmininet/tests/__init__.py — non-root runs auto-skip root tests.

## Verified locally (non-root)
- `./scripts/run-tests-local.sh test_pure.py test_misc.py test_link.py` → 62 passed, 12 skipped, 1 warning
- Full suite collects: 193 tests
- shellcheck clean on scripts/*.sh

## Deferred tasks (follow-up PR, AFTER this one merges)
1. **Reformatting-only PR** — ruff format + mdformat across the codebase (commit 659f19e has the full list; ~111 files). Add ruff config (pyproject `[tool.ruff]`, ~25 rule groups, per-file-ignores), mdformat (`.mdformat.toml`), shellcheck.
2. **Pre-commit hooks** — `.pre-commit-config.yaml` with ruff/mdformat/etc. formatting+linting.
3. **CI lint steps** — add to all 3 workflows: `ruff check`, `mdformat --check`, `shellcheck`, no-noqa/type:ignore check, `.coveragerc` identity check.
4. **Coverage** — `.coveragerc` + `--cov=ipmininet/` in CI test runs (pytest-cov dep).
5. **install.py refactor** — skip-if-built guards, `compile_prefix` for multi-stage builds, `make_cmd()` helper, `--install-frrouting-compile` flag, PEP 668-aware pip install in-code (see commit 2490984 for reference). Enables multi-stage Containerfile compile caching.
6. **Multi-stage Containerfile** — deps/compile/final stages with gha caching (see c25a1ca Containerfile).
7. **GitHub issues to create** (after CI green):
   - `test_network_capture` broken — `mimidump` (from PR #2) never shipped; propose restoring tcpdump-based capture or shipping the binary.
   - any other non-fixable issues discovered.

## Hard rules / user constraints
- NEVER use `/tmp` for scratch — only `.tmp/` in the repo (gitignored).
- No `1.2.6` tag on the fork; tag upstream (`mimi-net`) ONLY after merge.
- Create GitHub issues only after CI passes.
- PR body must mention dependabot.
- No reformatting in this PR; no lint config; no pre-commit; CI lint steps deferred.
- Respect the 5-commit structure; amend via `--fixup` + `git rebase -i --autosquash 75290b9`.

## Commands / workflow
- Reset/recreate: `git reset --hard 75290b9`
- Fixup + rebase: `git add <file> && git commit --fixup=<sha> && GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash 75290b9`
- Force-push PR: `git push --force-with-lease origin fix/ci-clean`
- Update PR: `gh pr edit 11 --repo mimi-net/ipmininet --title ... --body-file .tmp/pr-body.txt` — NOTE: `gh pr edit` hits a GraphQL Projects-classic deprecation error and silently no-ops. Use instead:
  `gh api -X PATCH repos/mimi-net/ipmininet/pulls/11 -f title="..." -F body="$(cat .tmp/pr-body.txt)"`
- PR view: `gh pr view 11 --repo mimi-net/ipmininet --json ...`
- CI runs: `gh run list --repo mimi-net/ipmininet --json databaseId,headSha,status,conclusion,name`
- Job detail: `gh run view <RUN_ID> --repo mimi-net/ipmininet --json jobs`
- Logs: `gh run view <RUN_ID> --repo mimi-net/ipmininet --log-failed`
- Local non-root run: `./scripts/run-tests-local.sh ipmininet/tests/test_pure.py ipmininet/tests/test_misc.py ipmininet/tests/test_link.py`

## Repo / remotes
- origin = iakov/ipmininet (fork), upstream = mimi-net/ipmininet (admin push), cnp3 = cnp3/ipmininet
- Backup branch: `safety/full-work-original` (old full work, at df93e95). Diff vs current HEAD should be 0 files (content-equal).
- Working branches: fix/ci-clean (active PR), hotfix-ci, fix/ci-dev-tooling, master (origin).
- Base 75290b9 = "Merge pull request #9" — upstream master was force-pushed back here; tag 1.2.6 deleted from both mimi-net and iakov fork.

## Scratch files in .tmp/
- pr-body.txt (PR body), bm-log.txt, ci-log.txt, container-fail.log (diagnostics)

## Rootless podman testing (branch: rootless-tests)
Branched off fix/ci-dev-tooling (5532a14). Commits: 406ca05 (runner+probe+prep),
2dcfbfe (docs), 6294f79 (podman machine fallback).

### Confirmed on rootless dev host (podman 6.1.0, uid 1000, kernel 7.0.0, OVS module loaded)
- ALL kernel primitives work in a rootless container: netns create + setns entry,
  veth across ns + ping, LinuxBridge+STP, sysctls (ip_forward + seg6_enabled),
  OVS kernel datapath (add-br), raw IPv6 socket, bind port 53.
- Minimal caps: `--cap-add=NET_ADMIN,SYS_ADMIN` ONLY (NET_RAW/NET_BIND_SERVICE are
  in podman defaults). Must keep default (pasta) network — NEVER `--network=host`
  (that ns is owned by init userns; no CAP_NET_ADMIN there).
- /proc/sys is mounted RO in non-privileged podman → netns sysctl writes give EROFS.
  Fix: `mount -o remount,rw /proc/sys` (in scripts/rootless-prep.sh, run before tests).
- `ip netns exec` is broken in userns ("mount of /sys failed: Operation not permitted")
  but mininet uses mnexec (setns by pid) — irrelevant. Probe uses nsenter instead.
- mininet logs "Error setting resource limits" (cgroup CPU in userns) — benign warning,
  but tests run SLOWER (no CPU pinning). Full ~190-test suite takes many hours.
- Gate tests pass rootless: test_addr_intf (StaticAddressNet, 13s), test_misc.py
  (all, incl. require_root), test_link.py (2 pre-existing branch failures in
  test_ordered_address — Python 3.12 ordering bug, unrelated to rootless, fixed on
  fix/ci-clean branch), test_static.py 6/6 (~10 min).
- OVS module must be loaded ON THE HOST (container can't modprobe): one-time
  `sudo modprobe openvswitch`. Only needed for OVS-only tests.

### Commands
- Build: `podman build -t ipmininet-dev -f Containerfile .` (~20 min, compile FRR)
- Probe: `scripts/rootless-ci.sh scripts/rootless-probe.sh`
- Minimal caps run: `ROOTLESS_CAPS=NET_ADMIN,SYS_ADMIN scripts/rootless-ci.sh <tests>`
- Privileged: `ROOTLESS_CAPS=privileged scripts/rootless-ci.sh <tests>`
- Full matrix (slow): `.tmp/matrix.log` — running in background.
- Fallback: `scripts/podman-machine-ci.sh` (QEMU VM in user session, rootful inside VM).

### Rootless subset matrix results (privileged caps, 36 min): 45 passed / 15 failed
PASS: ospf, ospf6, bgp(daemon_params), ripng, radv, switch(STP), tc, cli,
physicalinterface, topologydb(OVS kernel datapath), address_alllocation,
linkfailure, misc, link, static.
FAIL root-causes:
- test_dns (5): named dies in userns — named.py startup_line has `-t /`, making
  named's cwd `/` "not writable" for userns-root → "loading configuration:
  permission denied". Fix: drop `-t /` (no-op chroot in rootful). VERIFIED:
  named works in container WITHOUT `-t /`, dies WITH it.
- test_srv6 (7): `ip sr tunsrc set ::` → EPERM in userns even with --privileged.
  GENUINE rootless blocker (kernel seg6 genl). Needs podman machine/rootful.
- test_sshd (1): pre-existing `/run/sshd` missing (fixed on fix/ci-clean PR branch).
- test_gre (1): `ip tunnel add` fails — `ip_gre` kernel module not loaded on
  host; container can't modprobe. One-time host prereq: `sudo modprobe ip_gre`.
- test_iptables (1): `iptables` package missing from Containerfile image (RuntimeError).
- OVS module was loaded on host → topologydb OVS kernel datapath PASSED in userns.
- Minimal caps re-validated on routing test (test_ospf_example) — running.

### podman machine fallback: VALIDATED end-to-end
- gvproxy was NOT installed (podman machine start fails). User ran `sudo apt install gvproxy`.
- gvproxy installs to /usr/bin; podman searches libexec dirs → set user-level
  containers.conf: [engine] helper_binaries_dir = ["/home/me/.local/libexec/podman"]
  (dir with symlinks to gvproxy + netavark/aardvark-dns/catatonit/quadlet/rootlessport).
- virtiofsd missing too; podman machine requires it for host mounts. Workaround:
  removed machine Mounts from ~/.config/containers/podman/machine/qemu/ipmininet.json
  → start works without virtiofsd (script syncs repo via ssh/tar, no file share needed).
- podman machine inspect --format '{{.State}}' returns lowercase "running".
- Test-run failure: mounting workspace over /workspace hides image venv (/workspace/.venv
  has pytest). Fixes: ci-test.sh now mkdir -p /workspace/.tmp + forwards
  UV_PROJECT_ENVIRONMENT through sudo env; podman-machine-ci.sh runs uv sync --all-extras
  with UV_PROJECT_ENVIRONMENT=/opt/venv before ci-test.sh (venv outside mount).
- Containerfile bug: `touch /workspace/.tmp` made it a FILE (tee errors); fixed to mkdir.
- Result: scripts/podman-machine-ci.sh test_addr_intf PASSED in VM (13.8s).
- Machine ipmininet left running (qemu 4cpu/4g/100g).

### Machine recreation at 20 GiB with virtiofs (fdf2d4f)
- Recreated: `podman machine rm -f ipmininet` → `podman machine init --cpus 4 --memory 4096 --disk-size 20 ipmininet`.
- virtiofsd host mounts restored ($HOME + /etc/containers via virtiofs) → interactive
  `podman run -v` inside the machine works against host paths. Performance: near-native.
- Symlinked: `/usr/libexec/virtiofsd → ~/.local/libexec/podman/virtiofsd` so helper_binaries_dir finds it.
- Disk: 20GiB virtual, 2.2GiB used inside, 18GiB free (vs 93% free on the 100GiB disk).
- `PODMAN_DISK_SIZE` env (default 20) in the script; `PODMAN_ALLOW_NO_VIRTIOFSD=1` override for no-mount fallback.

### PR #11 final (named fix + description)
- Added 6th commit `0fb8522 fix: remove -t / from named startup line` — SIGNED (SSH),
  GitHub verified:true. Local `%G?` now shows G after configuring
  ~/.config/git/allowed_signers (user.set allowedSignersFile).
- Note: the earlier `git commit -S` DID produce a signed commit even though local
  %G? showed N — N was a local verification artifact (missing allowedSignersFile),
  not a missing signature. GitHub API confirmed verified:true.
- PR #11 body updated via gh api PATCH (pr-body.txt): added commit #6 + "Validation
  notes (rootless container)" section. gh pr edit still no-ops (GraphQL Projects).
- PR #11: OPEN, MERGEABLE, head 0fb8522.

## RETROSPECTIVE (this session) — remember this

### What was good (keep)
1. Probe-first bisection (rootless-probe.sh primitives) — biggest time-saver.
2. Scripted run wrapper (rootless-ci.sh + ROOTLESS_CAPS env) — one-command iteration.
3. `setsid cmd > log 2>&1 </dev/null &` survives tool timeout-kill — use for all >2-min jobs.
4. Single-file bind-mounts into containers — iterate scripts without 20-min rebuilds.
5. Targeted repro over source-reading: dns-diag.py ran `named -g`, found fatal in one run.
6. Classify failures rootful-vs-rootless before fixing.
7. Repo-local commit.gpgsign=false — no per-commit signing failures on feature branches.

### What was bad / wasted time
1. `pkill -f "podman run"` killed my own shell (pattern matched own cmdline); repeated with pgrep.
2. Full ~190-test container matrix killed at 5% after 50 min (userns = no CPU limits = slow).
   Representative subset was the right call; switch sooner.
3. Named rabbit hole: read named.py/host-config/process-manager for rounds before writing repro.
4. Redundant `podman build --target final` to "verify image exists" — wasted 180s; check state instead.
5. Signing false alarm: claimed 0fb8522 unsigned from `%G?=N`; it WAS SSH-signed, GitHub verified:true.
   `N` w/o allowedSignersFile = verification artifact, not proof unsigned.
6. Porting named fix: `git diff` polluted by reformatting; `git checkout <branch> -- file` staged a revert.
   Extract minimal hunk first; work on target branch immediately.
7. Containerfile `touch /workspace/.tmp` = file not dir → `tee: Not a directory` twice before fixing to mkdir.
8. 100 GiB machine disk: didn't check `podman machine init --help` default; user flagged it.

### Quirks that save time (memorize)
- setsid+log is the only reliable >2-min job pattern here.
- `uv run --with shellcheck-py shellcheck` when shellcheck not installed.
- `gh api -X PATCH .../pulls/N -F body="$(cat f)"` — `gh pr edit` silently no-ops (GraphQL Projects).
- `ip netns exec` broken in userns (/sys mount) but nsenter works; mininet uses mnexec (setns) → irrelevant.
- `/proc/sys` ro in non-privileged podman → `mount -o remount,rw /proc/sys` unblocks net-sysctls.
- Minimal caps = NET_ADMIN,SYS_ADMIN (NET_RAW/NET_BIND_SERVICE are podman defaults).
- `git stash -- <path>` discards accidental cross-branch checkout.
- Verify via podman ps / gh api / du (source of truth), NOT pgrep patterns.

### Improvements (my remembered answers)
1. Probe lowest primitive first; scale layers (primitive→single→file→subset); downshift if slow.
2. Capture failing component's own stderr/log first; write repro before reading framework internals.
3. Never pkill/pgrep by pattern matching own cmdline; use explicit pids/podman ps.
4. Signing: verify via `gh api .../commits/<sha> --jq .commit.verification` first; treat local N as ambiguous.
5. Check CLI --help defaults before creating resources (disk-size, memory).
6. After editing a script, re-chmod +x and run bash -n + shellcheck immediately.
7. Porting between branches: extract minimal hunk, apply on target branch, never blind `checkout <branch> -- <file>`.
8. Fold findings into PR description as discovered, not a final pass.
9. Reuse image+venv (expensive), inject changes via mounts/env; rebuild rarely.

## 2026-08-26 DNS CI regression investigation (PR #11 head 0fb8522)

### Failure
- Bare-metal job run 32967635530 on head 0fb8522 FAILED: 6 DNS tests (test_dns_network x5 + test_zone_delegation), 179 passed, 1 skipped. All: `dig @localhost -p 53` -> connection refused (named never listening). Failure at test_dns.py:85 (assert_dns_record), NOT at config check (dry_run passed, net.start() ok).
- Earlier passing runs: ccdefd8 (run 32884328552), eda2664 (32883432374). ONLY diff between ccdefd8 and 0fb8522 = named.py: removed `-t /` from startup line.

### Bias-check / confounders (IMPORTANT)
- NOT proven that -t / removal caused it. Confounder: GitHub rolled ubuntu-24.04 image between runs. Passing run upgraded bind9 .5->.6 (image had .5 preinstalled); failing run fresh-installed .6 (image lacked it). Base images differ.
- Earlier failing runs (10ead26 etc.) had -t / PRESENT but failed at DIFFERENT stage (mnexec/ifconfig missing = mininet not installed). Not evidence against -t /.
- Mechanistically -t / (chroot to /) should be no-op rootful. Commit msg claimed "rootful behavior unchanged."
- Our rootless container validation: test_dns PASSES with -t / removed. Same code change passes in container, fails on bare-metal -> suggests ENVIRONMENT, not code.

### Suspected real cause (bare-metal)
- aa-exec -p unconfined wrapper only used if has_cmd("aa-exec"). New runner image likely lacks apparmor-utils -> aa-exec absent -> named runs AppArmor-CONFINED (Ubuntu bind9 profile in enforce) -> can't write session.key/log in node cwd -> dies -> connection refused. Independent of -t /.

### Container experiments (ipmininet-dev image)
- named runs fine WITHOUT -t / in container (profile NOT loaded in container apparmor namespace; no aa-exec present).
- After `apt-get install apparmor-utils`, aa-exec present and `aa-exec -p unconfined` works in ROOTFUL container; named via wrapper starts fine.
- In ROOTLESS userns container (--userns=auto): aa-exec NOT found after apt install (apt install may have failed in userns — NEEDS RETEST; PATH? apt error suppressed). MUST VERIFY before making wrapper unconditional.

### User-approved plan (build mode)
1. install.py: install apparmor-utils (Ubuntu/Debian) in install -a / named flow.
2. named.py startup_line: make aa-exec -p unconfined UNCONDITIONAL (drop has_cmd gate) — ONLY if aa-exec reliably present in all envs (bare-metal + container + rootless userns). VERIFY userns first.
3. container-test.yaml: add test_dns.py to test list (Containerfile already has bind9+dnsutils).
4. Time cost of DNS in container: measure (bare-metal passing run: test_dns.py module ~5min17s; per-test 46-47s x5 + zone_delegation 71s + etc_hosts 6/18/20s + gap).
5. Document all findings in commit msg + PR description separate "Flaky test analysis" section.

## 2026-08-26 CI dispatch outage
- Commit 2422051 pushed to fix/ci-clean but NO workflow run dispatched (both iakov push + mimi-net pull_request).
- Investigated: YAML valid (parsed locally + raw compare ok), workflows active on both repos, actions enabled, PR head correct (2422051), no check-runs/statuses created.
- Root cause: GitHub Actions MAJOR OUTAGE started 2026-08-26 15:11 UTC (database primary failover, throttled inbound traffic) - status.github.com. Push at 15:51 UTC fell in the outage window.
- Action: wait for recovery, then re-push to re-trigger dispatch.

## 2026-08-27 CORRECTED root cause (AppArmor theory REFUTED)
- Installed Docker locally (official docker repo already configured; docker-ce 29.7.2; coexists with rootless podman).
- Reproduced the CI container DNS failure locally with Docker (old image, NO apparmor-utils): 6 failed / 3 passed - EXACT match to CI.
- Probed: `docker run --privileged` => AppArmor profile "unconfined" (NOT docker-default). So AppArmor is NOT enforced in CI container. The apparmor-utils/aa-exec theory is dead.
- Real root cause: named runs `-u root` which drops CAP_DAC_OVERRIDE (keeps NET_BIND_SERVICE + SYS_RESOURCE). Daemons launched via node.popen (mnexec -da) inherit the PYTEST cwd, not node.cwd. On CI that cwd is a non-root-owned 755 dir (checkout/workspace) => named can't write session.key/_default.tsigkeys => "loading configuration: permission denied" => dies => connection refused.
- podman never reproduced because rootless podman maps container root to host user => workspace root-owned inside container => writable.
- `-t /` was a red herring (masked the bug by chdir'ing to root-owned / on rootful), BUT its removal (0fb8522) is still CORRECT for rootless (userns root can't write /; verified: restoring -t / fails in rootless podman 6/9).
- Fix: `cwd=self.cwd` on daemon popen in __router.py start() + start_daemon(). Verified 70/70 (test_misc+test_pure+test_dns) in BOTH docker and podman.
- Reverted apparmor-utils changes (install.py, Containerfile, named.py comment) - wrong theory. Amended 2422051 -> e5a5b6e "fix: run node daemons in the node working directory" (keeps container-test test_dns, adds cwd fix, drops apparmor stuff).
- Next: force-push, monitor CI, update PR body (done in .tmp/pr-body.txt).
- Lesson (from user): assumptions may be wrong; OK to reassure and correct later. This is product/process/self-development.
