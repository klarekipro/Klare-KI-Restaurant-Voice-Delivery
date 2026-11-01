# Agent handoff protocol

Git is authoritative for committed code, decisions and handoff records. Before work, receiving agents run `git status --short --branch`, `git log -3 --oneline`, `git fetch origin`, `git ls-remote --heads origin`, and `git worktree list`. Validate recorded SHAs, remote tracking and files; never assume another agent committed or published its work.

One primary writer per worktree. Concurrent work requires separate worktrees and feature branches. No overwrite, force push, destructive reset/clean or automatic merge. Model/provider changes preserve requirements and progress; manual provider switching uses this protocol, without switching infrastructure.

Before handoff:
1. Validate completed changes, record exact commands, outcomes, failures and remaining limitations.
2. Update CURRENT_STATE, TASK_BOARD and DECISION_LOG, with source SHA, validated implementation SHA, branch, remote and next task. A handoff-record commit can refer to its implementation parent; receiving agent resolves the final handoff SHA with `git rev-parse HEAD`.
3. Record uncommitted/untracked files, known defects, blockers and next actionable task. Never commit databases, session keys, credentials or sensitive information.
4. Commit and publish validated changes to the feature branch; verify remote SHA and PR base/head. Do not declare handoff complete while required changes remain local.
5. Receiving agent independently checks actual behavior and evidence; claims from Claude Code and Codex require evaluation regardless of provider.

Safety: local synthetic-data work only. No production, VPS, paid APIs, privileged MCP or real telephony without explicit approval. Published demo account passwords are local-only: bind to 127.0.0.1, never expose this app on public networks. Feature/release approval is not production approval.
