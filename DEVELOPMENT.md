# Development notes

This file is `[describing]` — it explains rationale and design context.
For agent behavior rules and commands, see `AGENTS.md`.

## Version pinning strategy

`pyproject.toml` uses intentionally loose constraints (e.g. `mako>=1.1`).
`uv.lock` is the lockfile that pins exact versions. This keeps `pyproject.toml`
clean while providing reproducible builds. After any `pyproject.toml` version
adjustment, run `uv sync --all-extras --upgrade` and commit the updated
`uv.lock`.

## Type safety stance

This codebase does not use mypy. The `ConfigDict` pattern (attribute-style dict
access) is pervasive in the daemon config system and is fundamentally
un-typeable. Ruff's lint rules (25 groups) cover real error classes — undefined
names, unused imports, mutable defaults, loop variable capture — without the
annotation burden that mypy would require.
