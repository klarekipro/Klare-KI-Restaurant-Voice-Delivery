# Current state — Mission 04

Active implementation: feat/local-agent-runner, separate worktree /Users/admin/Projects/restaurant-agent-runner. Source PR3: 7b13ba55f66c7214143dc00aadbca8435a0a1d05. Resolve final handoff commit with git rev-parse HEAD and compare origin before writing. Existing MVP and hardening worktrees were not modified.

Runner entry: python3 tools/agent-runner/runner.py. Read tools/agent-runner/README.md and outputs/codex/mission-04/VALIDATION.md. Current mission state lives in ignored .agent-runner/state.sqlite. Model/provider changes must continue from records, not assumptions.

Real review 3ca428d18423: COMPLETED, Claude→Codex with automatic handoff and external compile checks; two attempts unchanged after separate-process resume. Real repair 92bd71a914ab: WAITING_APPROVAL following API429 with partial uncommitted template change. Preserve .agent-runner/worktrees/92bd71a914ab; no destructive cleanup. Its hash is recorded in real-limit-hold.json. Claude availability is unavailable with unknown machine retry timestamp. Historical holds are not automatically approved.

Validation commands:
- python3 -m unittest discover -s tools/agent-runner -p 'test_*.py' -q — 23 passed.
- Prepared project .venv from requirements-local.lock; original 22 app tests and scripts/local_acceptance.py passed in isolated loopback-only validation.
- `.venv/bin/python -m pytest -q` — 22 application tests passed (default pytest discovery excludes tools); runner suite is run separately. `.venv/bin/python -m pip check` and `git diff --check` passed. One existing Starlette/httpx deprecation warning remains.

Intentionally ignored: state SQLite/WAL/lock, private mission worktrees, .venv and caches. No DB/auth material committed. Main feature worktree should be clean after publication; receiving agent must verify actual status and remote SHA. Do not merge automatically or expose demo passwords publicly.

Next task: review runner security/state transitions and evidence independently. Inspect the preserved repair before operator approval or a new authorized continuation; use Codex if Claude capacity is still exhausted. Add safely scoped browser/mobile acceptance; neither HTTP nor compile checks constitute browser verification. Complete deferred application tasks listed in TASK_BOARD.
