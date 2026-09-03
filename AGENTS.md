# AGENTS.md — standing rules for this repo (branch `me/agentic`)

These are the durable working rules for agent (and human) sessions on this
repo. Load them at the **start of every session** and follow them during work.

## Where things live

- `master` tracks `mimi-net/master` (the fork where real PRs are opened/merged).
  `cnp3` is the canonical upstream (read-only reference); `origin` is our fork
  `iakov/ipmininet`. See `agentic/CI-LESSONS.md` for the full topology and the
  safe merge workflow.
- **`me/agentic` is the canonical branch for docs/knowledge.** It holds `agentic/`
  (knowledge docs + diagnostic tooling). It does NOT go to upstream.

## Knowledge rules

1. **Never push docs/knowledge to upstream without an explicit, unbiased user
   prompt.** Do not assume "keep it useful" means upstream — it does not.
2. The only docs allowed to change on upstream branches are docs **already
   present upstream**, and only to keep them consistent with code/test changes
   in the same PR.
3. When the user says **"remember"**, find the best doc in the docs corpus
   (`agentic/`, or an upstream doc if it is code/test-consistency related) and
   store the knowledge there. Do not rely on the chat.
4. **The session/chat is ephemeral — never trust it.** Trust docs. Before each
   run / at session init, look at this branch (`me/agentic`) and re-read the
   rules.
5. After pushing a feature/other branch, update the docs on `me/agentic` and
   push that branch too, so knowledge stays fresh.

## Workflow rules

- Never push directly to `mimi-net` master; master only changes via merged PRs.
- Do not commit docs/knowledge changes onto feature branches destined for
  upstream — keep them on `me/agentic`.
- After merging a PR: sync local master
  (`git checkout master && git fetch mimi-net master && git merge --ff-only`),
  delete the merged branch locally and on `origin`.
- `.tmp/` is git-ignored scratch. Do not commit anything from it unless the user
  explicitly asks; `gh-token.txt` there is a credential and must never be
  committed anywhere.
