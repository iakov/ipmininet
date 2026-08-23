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
- **Doc commits first**: Doc updates go in a separate commit or before the final cleanup commit, never mixed with code.

### Dependencies

- **`mininet`** is pinned to `mimi-net/mininet.git` fork — do not change to the official repo.
- **Version constraints**: `pyproject.toml` uses loose constraints; exact pins in `uv.lock` [→ DEVELOPMENT.md for rationale].
- **`uv.lock` must stay in sync**: Run `uv sync --all-extras` after every `pyproject.toml` change. Commit the updated `uv.lock` together with the `pyproject.toml` change — never separately.

### Testing

- **`install -a`** must run before tests — installs FRRouting, mininet, radvd, etc. via `ipmininet/install/install.py`
- **Root tests** via podman only (keeps host safe). See Commands section.
- **Coverage**: two identical `.coveragerc` files — root-level alias and `ipmininet/.coveragerc` (CI target).
- **OpenR tests** are `@pytest.mark.skip` — external build required, not run in CI.

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

# Root test (podman)
podman build -t ipmininet-dev .
podman run --rm --privileged -v $PWD:/workspace:Z ipmininet-dev \
    sudo env "PATH=$PATH" uv run pytest --cov-config=.coveragerc --cov=ipmininet/ -v
```

## Content triage [prescribing]

Every piece of knowledge goes to the highest-priority source:

1. **Code / config / scripts / tests** — executable source of truth
1. **AGENTS.md** — agent behavior rules, execution commands, repo-specific gotchas
1. **DEVELOPMENT.md** — everything else useful that does not fit above

If something can be expressed as a CI gate, script, or config check, do it there instead of documenting.

## Project conventions [prescribing]

- `.tmp/` — scratch directory in project root. Gitignored. Use for temp scripts, outputs, helper tools.
