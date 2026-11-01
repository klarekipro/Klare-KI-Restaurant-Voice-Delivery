# Local agent runner (experimental)

Requires Python 3.11+, macOS `sandbox-exec`, installed authenticated Claude Code and Codex. No new dependencies. Source baseline: PR3 `7b13ba5`. Backends inspected against Claude 2.1.119 and Codex 0.166.0. Other platforms fail closed.

From a clean repository worktree:

```
python3 tools/agent-runner/runner.py start tools/agent-runner/review-pr3.json
python3 tools/agent-runner/runner.py status
python3 tools/agent-runner/runner.py pause
python3 tools/agent-runner/runner.py resume
python3 tools/agent-runner/runner.py stop
python3 tools/agent-runner/runner.py report
python3 -m unittest discover -s tools/agent-runner -p 'test_*.py' -v
```

Use `--state /absolute/private/path/state.sqlite` before the command for another persistent store. It contains sensitive provider output and is ignored by Git. Reports are local, not automatically published. The mission definition is trusted operator input; repository instructions and model output are untrusted. Check IDs are fixed in code; no shell command strings. `compile` only establishes syntax validity, not functional readiness. `pytest` and `acceptance` require a prepared Python environment in the task worktree; no dependency installer is run automatically.

Single writer enforced by state-directory OS lock, unique mission worktrees and sequential execution (`max_concurrent=1`). Pause applies at next invocation boundary; stop prevents further invocations, current child has a hard duration bound. Recovery of uncertain in-flight execution holds for inspection rather than repeating possibly completed actions. No automatic approval grant: WAITING_APPROVAL cannot be cleared by resume. Inspect/terminate an orphan process and preserve the worktree before creating a new explicitly authorized mission.

The OS sandbox denies user-home reads except CLI/runtime paths, the task worktree and private scratch; writes are limited to task/scratch. Environment is allowlisted, clean provider HOME has only provider authentication. MCP/user settings are excluded. Claude project roles remain available. Provider edits trigger an approval boundary BEFORE test execution or commit; no autonomous execution of newly generated code. This conservative initial policy supports automatic review/handoff/check cycles, not unattended code repair publication. No push/merge/deployment is implemented.

Both limits and generic failures are bounded. Only machine error codes classify confirmed provider limits; prose claiming a limit is unconfirmed and holds. Retry times remain unknown unless available; availability is persisted. No cross-provider hard dollar cap is claimed: mission monetary-cap requests fail closed, Claude additionally gets its native $1 invocation budget. Duration/invocation/retry/consecutive-failure limits remain primary controls. Raw errors/usage are retained locally; reporting requires manual redaction before sharing.

Authentication may fail in the clean HOME; runner must hold or fail rather than enabling broad HOME access, unrestricted permissions or credential environment inheritance. Review verification evidence before using this prototype autonomously.
