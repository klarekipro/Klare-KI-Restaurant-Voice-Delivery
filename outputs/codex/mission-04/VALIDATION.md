# Mission 04 verification

Base: PR3, 7b13ba55f66c7214143dc00aadbca8435a0a1d05. Separate worktree and feature branch: feat/local-agent-runner.

Installed: Claude Code 2.1.119; codex-cli 0.166.0. Flags selected from actual CLI help. Claude uses outer macOS Seatbelt plus dontAsk/tool allowlist; Codex uses native named filesystem permissions (no unrestricted mode). Both perform positive execution and negative read/write probes. Broad HOME inheritance is disabled. Existing provider authentication only: copied Codex auth into private temporary HOME and Claude OAuth from its named Keychain entry. Credentials never enter committed reports.

Real review mission 3ca428d18423 completed with Claude exit 0 (145.07s), automatic persisted handoff to Codex exit 0 (42.34s), and external compile checks after both. Structured responses and usage are in real-review-cycle.json. Compile establishes syntax validity, not product correctness. A separate resume process observed COMPLETED and retained exactly two attempts. No manual copying of prompts/results occurred.

Additional real Codex-only probe completed a structured review with the native profile. Initial attempts exposed clean-HOME auth failure, a missing loader root-directory permission, and nested Seatbelt incompatibility. These were fixed without enabling unrestricted access. Failed attempts remain in the private state database.

Real repair mission 92bd71a914ab reached Claude API status 429 after changing call_simulator.html. The original parser did not recognize api_error_status and safely held the dirty worktree without claiming success. The parser now recognizes structured 429, persists availability, and supports authorized app-only unvalidated checkpoints before fallback. Those corrected paths are tested with mocks; the exhausted Claude quota was not re-run. The historical hold is deliberately not auto-approved. Partial changes remain in .agent-runner/worktrees/92bd71a914ab and their hash is recorded in real-limit-hold.json. No partial repair is published.

Tests: `python3 -m unittest discover -s tools/agent-runner -p 'test_*.py' -q` covers 23 cases: success/review, reverse repair, provider limits and fallback, dirty checkpoint, both unavailable, malformed result, approval, crash hold, reopened-SQLite continuation without duplicate attempts, bounded retries/invocations/duration, terminal transitions and lock conflict. Most fault scenarios use mocked adapters; no real provider-limit takeover is claimed.

Independent sandboxed application validation on unchanged PR3: original 22 tests passed and scripts/local_acceptance.py passed using prepared .venv and loopback-only network. This checks real HTTP lifecycle and process restart, not browser/mobile interaction. No browser or device acceptance was performed by this runner.

Remaining: review generated code before promoting checkpoints; add browser infrastructure under explicit safe scope; complete/validate preserved repair after capacity returns; stress OS termination/race cases beyond mocks; retain strict dependency/configuration gates. Only concurrency=1 is supported. Hard cross-provider monetary caps are rejected because billing cannot be measured/enforced globally. Duration and invocation caps are enforced; Claude's native budget flag is an additional provider guard, not a global monetary guarantee.

State is private and persistent in .agent-runner/state.sqlite; it is intentionally not committed. Startup/operator commands are documented in tools/agent-runner/README.md. No restaurant request process imports the runner, no paid service activation, force push, deployment or merge was performed.
