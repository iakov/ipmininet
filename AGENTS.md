# ipmininet — AGENTS.md

## Repo chain [describing]

```
iakov/ipmininet  →  mimi-net/ipmininet (upstream)  →  cnp3/ipmininet (original)
```

No PRs to upstream. Feature branches merge via PRs inside `iakov/ipmininet`.
Tests live in `ipmininet/tests/`.

## Quick start [prescribing]

```bash
uv sync --all-extras
uv run ruff check .
```

## Guardrails [prescribing]

All hard rules. No exceptions. Every mistake must produce a prevention measure — a CI gate, a script, or a doc rule.

All `[prescribing]` rules are MUST or SHOULD. Each MUST rule must be enforced by a CI gate or script. Rules without enforcement drift.

### Execution

- **Every Python command must use `uv run`**. Never bare `python`, `python3`, or `pip` — they bypass `.venv` and hit system packages.
- **`.python-version`** is the single source of truth for Python. CI reads it. No `actions/setup-python` in CI.
- **Root**: `sudo env "PATH=$PATH" uv run ...` — the `PATH=$PATH` preserves the uv `.venv` under sudo. Without it, `sudo uv run` resolves to system python.

### Code quality

- **Ruff**: 25 rule groups — see `pyproject.toml` for the full list and per-file-ignores
- **Zero `# noqa`** in `.py` files (one legit exception: `import mininet  # noqa` in `__init__.py`)
- **Zero `# type: ignore`** — CI gates both in `.github/workflows/test.yaml`
- **Pre-commit**: run `pre-commit install` once after cloning. Hooks:
  - `trailing-whitespace`, `end-of-file-fixer`, `check-merge-conflict`,
    `check-added-large-files`, `check-ast`, `detect-private-key`
  - `ruff --fix` on staged `.py` files
  - `mdformat --fix` on staged `.md` files
- **Lint before every commit**: `uv run ruff check . --fix` then `uv run ruff check .`

### Commit workflow

- **TDD**: Write the test, see it fail, implement, see it pass.
- **Git Flow**: Feature branches (`fix/*`, `chore/*`). Merge into `master` via PR inside `iakov/ipmininet`. No direct pushes to master.
- **Retro before push**: Before every publish (push, PR), review the session for mistakes and fix them mid-session. Do not batch fixes after push.
- **Pre-PR full validation**: Before opening a PR, run the full rootless container test suite:
  `scripts/ci-test.sh ipmininet/tests/`. This ~2-hour validation matches the heavy CI that runs
  on master merge.
- **Doc commits first**: Doc updates go in a separate commit or before the final cleanup commit, never mixed with code.

### Dependencies

- **`mininet`** is pinned to `mimi-net/mininet.git` fork — do not change to the official repo.
- **Version constraints**: `pyproject.toml` uses loose constraints; exact pins in `uv.lock` [→ DEVELOPMENT.md for rationale].
- **`uv.lock` must stay in sync**: Run `uv sync --all-extras` after every `pyproject.toml` change. Commit the updated `uv.lock` together with the `pyproject.toml` change — never separately.

### Testing

- **`install -a`** must run before tests — installs FRRouting, mininet, radvd, etc. via `ipmininet/install/install.py`
- **Root tests** via container only (keeps host safe). See Commands section.
- **Coverage**: two identical `.coveragerc` files — root-level alias and `ipmininet/.coveragerc` (CI target).
- **OpenR tests** are `@pytest.mark.skip` — external build required, not run in CI.

### First-fail diagnostics

- **Every CI command must pre-arm its most likely failure mode** so the first run is diagnostic-complete.
  Re-running with "more logging" is a fault — fix the command flags instead.
- **pytest must always use**: `-p faulthandler` (dumps stack on crash),
  `--showlocals --capture=tee-sys --tb=long` (full context on assertion failure).
  Timeout config (`timeout = 300, timeout_method = "thread"`) is in `pyproject.toml` — do not duplicate in scripts.
- **Install commands must tee stdout+stderr to a known file path** so failure logs are always available
  for post-mortem. If output takes >1 minute to generate, pre-redirect to a file.
- **Never re-run without diagnosis**: Before cancelling or retrying any CI run, extract ALL available
  diagnostics — the last test name, the last log lines, the step that timed out, the error type.
  Each run is a data collection opportunity, not a coin flip.
- **Read the full output, not just the tail**: When output is truncated, the saved file may contain
  errors earlier than the last visible line. Use Read or Grep on the full output to collect ALL
  distinct failure modes before fixing any. Re-running with one more fix is a fault — collect
  every fix from the first failed run. Examples: missing apt packages (pip3, wget), missing
  config files, permission errors — all visible in the full log.
- **Ask before re-running**: "What will the next run tell me that I don't already know?"
  If the answer is "nothing" or "I don't know", stop and read the existing output. A re-run
  that produces no new information is pure waste.

### Storage-for-time tradeoff

- **Storage is cheap, time is expensive**. Pre-bake heavy containers with all dependencies and compile
  artifacts so local iteration is fast (seconds vs. 20-min rebuilds). Accept the one-time build cost.
- **Recoverable layers in containers**: Split `RUN` instructions so earlier cached layers are reused
  if a later step fails. Apt packages in one layer, compile in the next. Pay apt download once,
  retry compile cheaply.
- **`.dockerignore` excludes build artifacts** (`.venv`, `.git`, `__pycache__`), but **keeps tooling
  scripts** (`scripts/ci-*.sh`). Never exclude something the build needs.

### Local reproduction before CI

- **For any CI issue that takes >5 minutes to reproduce**, pre-bake a container image and iterate
  locally in seconds. Push to CI only after the fix is confirmed locally.
- **One variable per push**: change exactly one thing, push, observe, learn. If the outcome is the
  same as before, you learned nothing — revert and try a different variable.
- **Binary search, don't guess**: isolate the failure source by halving the search space.
  Never skip this step — guessing is gambling with wall-clock.

### Wall-clock budget

- **Every CI cycle costs real time and host resources** (CI servers are shared). Before pushing, ask:
  "What question does this run answer?" If the answer is "I don't know, let's see what happens" —
  don't push. Go learn locally.
- **A cancelled run produced zero data**. If you cancelled it, you failed to collect diagnostics
  beforehand. Let the run finish (or timeout) with diagnostics enabled.
- **Respect CI servers**: avoid brute-force debugging. Use local containers.
- **Respect local wall-clock**: pre-bake once, iterate fast.

## Architecture [describing]

How the codebase is wired:

- **Entrypoint**: `ipmininet/ipnet.py` (`IPNet`, extends `Mininet`)
- **Topology**: `ipmininet/iptopo.py` (`IPTopo`, extends `Topo`) — overlay pattern for AS, OSPF areas, BGP peerings
- **Router config**: `ipmininet/router/config/` — daemon config generators, Mako-rendered output
- **Host config**: `ipmininet/host/config/` — DNS (named), DHCP (dnsmasq)
- **Templates**: Mako, in `ipmininet/*/config/templates/`
- **`ConfigDict`** (`router/config/utils.py`): dict subclass with attribute access (`cfg.foo == cfg["foo"]`). Used throughout the daemon config system. Not typeable with current patterns.

### Adding a daemon [prescribing]

1. Subclass `Daemon` or `QuaggaDaemon` in `router/config/`
1. Create a Mako template in `templates/`
1. Register in `router/config/__init__.py` and the config class `daemons=` list

### Config flow [describing]

`Daemon.build()` → `ConfigDict` → `Daemon.render()` (Mako template) → `Daemon.write()` (writes file). Config checks run via `dry_run` property before daemon startup.

## Commands [prescribing]

```bash
# Sync and lint
uv sync --all-extras
uv run ruff check .
uv run ruff check pyproject.toml
uv run ruff check . --fix --unsafe-fixes  # also fix format strings in exceptions
uv run mdformat --check .  # check markdown formatting
uv run mdformat .  # fix markdown formatting

# Root test (container)
docker build -t ipmininet-dev -f Containerfile .
docker run --rm --privileged -v $PWD:/workspace:Z ipmininet-dev \
    sudo env "PATH=$PATH" .tmp/ci-test.sh ipmininet/tests/

# Run a single test file
docker run --rm --privileged -v $PWD:/workspace:Z ipmininet-dev \
    sudo env "PATH=$PATH" scripts/ci-test.sh ipmininet/tests/test_bgp.py

# Rebuild only the final stage (fast, ~30s) after source code changes
docker build -t ipmininet-dev -f Containerfile --target final .

# Rebuild only the compile stage (after install.py changes)
docker build -t ipmininet-dev -f Containerfile --target compile --network host .

# Faster iteration with podman volume (skips compile entirely if built)
podman volume create ipmininet-build
podman build -t ipmininet-dev --volume ipmininet-build:/root --network host .

# Diagnostic run with full timeout + faulthandler output
docker run --rm --privileged -v $PWD:/workspace:Z ipmininet-dev \
    sudo env "PATH=$PATH" scripts/ci-diag.sh ipmininet/tests/
# Diagnostic log written to .tmp/ci-diag-*.log

# Before PR: full 2-hour validation
docker build -t ipmininet-dev -f Containerfile .
docker run --rm --privileged -v $PWD:/workspace:Z ipmininet-dev \
    sudo env "PATH=$PATH" scripts/ci-test.sh ipmininet/tests/

# Build a specific stage for debugging
docker build -t ipmininet-deps -f Containerfile --target deps .
docker build -t ipmininet-compile -f Containerfile --target compile .

# View coverage report (open in browser)
python3 -m http.server 8000 --directory htmlcov/
```

## Content triage [prescribing]

Every piece of knowledge goes to the highest-priority source:

1. **Code / config / scripts / tests** — executable source of truth
1. **AGENTS.md** — agent behavior rules, execution commands, repo-specific gotchas
1. **DEVELOPMENT.md** — everything else useful that does not fit above

If something can be expressed as a CI gate, script, or config check, do it there instead of documenting.

## Project conventions [prescribing]

- `.tmp/` — scratch directory in project root. Gitignored. Use for temp scripts, outputs, helper tools.
- `scripts/` — promoted, clean, stable, shellcheck-passing scripts. Pre-push agent maintains them: stale scripts are removed or documented. See DEVELOPMENT.md#scripts-lifecycle.
