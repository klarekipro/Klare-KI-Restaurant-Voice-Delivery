# Current state — Mission 05

Branch: feat/autonomous-takeover-hardening. Worktree: /Users/admin/Projects/restaurant-takeover-hardening. Base: PR4 commit 96ee67214f7e92cd212705e8942d42accb665d04. Resolve final handoff SHA with git rev-parse HEAD and compare remote before work. No automatic merge or deployment approval.

Read tools/agent-runner/README.md and outputs/codex/mission-05/VALIDATION.md. SQLite state and private snapshots remain ignored in .agent-runner/. Original mission 92bd71a914ab is still held and its template hash is unchanged. Do not clean its worktree or the intermediate recovery worktrees.

Real recovery 2423183b75aa was independently rejected for a retry payload defect. Authorized follow-up 46ae6de714e3 COMPLETED using two real Codex processes, external checks and no manual result forwarding. Claude API429 is historical real evidence; reverse direction is simulated test coverage. Final repaired template is integrated byte-for-byte from verified commit 1587f11; full hashes and machine results are in live-recovery.json.

Commands: python3 -m unittest discover -s tools/agent-runner -p 'test_*.py' -q; reviewed-project .venv/bin/python -m pytest -q; .venv/bin/python scripts/local_acceptance.py; node tools/agent-runner/check_simulator.cjs app/templates/call_simulator.html. Expected: 36 runner tests, 22 app tests, HTTP/JS checks pass. One existing Starlette/httpx deprecation warning remains. No browser/mobile verification.

Next agent: review PR security and recovery transaction boundaries independently. Reproduce tests and CLI evidence. Existing complete missions must not execute again on resume. Failed review missions and historical approval holds must remain terminal/held; use explicitly authorized idempotent import/follow-up commands for bounded work. Keep local-only credentials and synthetic data restrictions.
