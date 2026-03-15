# AGENTS.md instructions for C:\Users\Sjack\Documents\Codex\AC_Career_Manager

## JCodeMuncher-First Policy

For any codebase exploration, impact analysis, or bug triage in this repository, use JCodeMuncher tools first.

Required order:
1. `mcp__jcodemunch__list_repos`
2. If repo not indexed: use `mcp__jcodemunch__index_repo` with `corveck79/ac-career-manager`
3. Use `mcp__jcodemunch__search_symbols`, `mcp__jcodemunch__get_file_outline`, `mcp__jcodemunch__get_symbols`, and `mcp__jcodemunch__search_text` to gather only relevant code
4. Only use full-file reads (`cat`/`Get-Content`/`rg` over entire files) when JCodeMuncher cannot retrieve required details

## Token Efficiency Rules

- Do not read whole files unless strictly necessary.
- Prefer symbol-level retrieval over file-level retrieval.
- Fetch at most the symbols required for the current task.
- Summarize findings from symbols before requesting additional code.

## Fallback Rules

- If `index_folder` fails due to path naming issues, index by GitHub repo: `corveck79/ac-career-manager`.
- If JCodeMuncher is unavailable or returns incomplete data, fall back to `rg` + targeted line reads.

## Scope

Apply this policy to all backend and frontend code tasks in this repository.
