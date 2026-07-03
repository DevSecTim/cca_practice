# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Practice code for the Certified Claude Associate – Foundations (CCA-F) exam, following the
**[CCA-F 14-Day Study Plan](https://www.finstor.in/wp-content/uploads/2026/03/CCA-F_14Day_Study_Plan.pdf)**
(an unofficial, community-created plan — not published or endorsed by Anthropic).
Each `dayN.py` / `dayN_notes.md` corresponds to one day of that plan and demonstrates a specific
Claude API / Agent SDK / Claude Code concept in isolation. `PROGRESS.md` tracks which days and
sub-resources have been completed — check it to see what's already done before assuming a "next day"
file needs to be created.

When asked to add a new day's exercise, first fetch/read the corresponding section of the study plan PDF
to get the exact points to implement, rather than guessing from the day number alone.

## Commands

```bash
# Environment (uv-managed, Python >= 3.14.2)
uv sync                       # install/sync dependencies from pyproject.toml / uv.lock

# Run any day's exercise
uv run python day2.py
uv run python day9.py

# ANTHROPIC_API_KEY must be set — it is loaded from .env (gitignored) or exported in the shell.
```

There is no build step, lint config, or test suite in this repo — files are standalone scripts run
directly with `python3`/`uv run python`. Do not invent test/lint tooling unless the user asks for it.

## Architecture / conventions across day*.py files

Every exercise script follows the same shape and should stay consistent with it:

- `client = anthropic.Anthropic()` at module scope, reading `ANTHROPIC_API_KEY` from the environment —
  never hardcode keys.
- Tool definitions are plain dicts (`name` / `description` / `input_schema`) assigned to a `tools` list,
  not wrapped in a helper/abstraction.
- Model choice is deliberate and part of the lesson: `claude-sonnet-4-5` for coordinator/primary calls,
  `claude-haiku-4-5` (or `claude-3-5-haiku-20241022`) for cheap subagents/extraction — preserve this
  distinction rather than defaulting everything to one model.
- The **agentic loop** pattern (`day2.py`, `day4.py`) always terminates on `response.stop_reason`
  (`end_turn` vs `tool_use`), never on a fixed iteration counter or by parsing assistant text — this is
  an explicitly tested anti-pattern in the exam material.
- Multi-agent scripts (`day4.py`, `day9.py`) implement the **hub-and-spoke** pattern: a coordinator
  explicitly collects each subagent's output and passes it forward by string interpolation — subagents
  never share memory or see each other's results.
- Structured-extraction scripts (`day7.py`, `day9.py`) force structured output via
  `tool_choice={"type": "tool", "name": "..."}` rather than `"auto"`, and use nullable fields
  (`{"type": ["string", "null"]}`) instead of letting the model fabricate missing data.
- Error handling for subagents/tools returns a structured object (`error`, `failure_type`,
  `partial_results`, `alternatives`, `is_retryable`) rather than a bare status string, so a coordinator
  can make a real decision (retry / proceed with partial results / flag a coverage gap).
- Policy enforcement that must be guaranteed (e.g. refund limits in `day8.py`) is implemented as a
  programmatic hook intercepting the tool call, not left to the system prompt — prompt-only rules have a
  non-zero failure rate per the exam material.

## Claude Code configuration in this repo

- `.mcp.json` — project-scoped MCP servers (committed; secrets referenced via `${ENV_VAR}`, never
  inlined).
- `.claude/rules/testing.md` — path-scoped rule (YAML `paths:` frontmatter) that only loads for
  `*.test.py` / `*.spec.py` files: use pytest (never unittest), test functions prefixed `test_`, mock
  external API calls with `pytest-mock`.
- `.claude/settings.local.json` — personal permission allowlist, not a source of project conventions.
