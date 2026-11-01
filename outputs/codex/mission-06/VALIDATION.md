# Mission 06 validation and operator record

Base: PR5, 8471c4d5215b80cb260a546d339291afe727630e. Worktree/branch: restaurant-quota-resume / feat/automatic-quota-resume. Existing worktrees, historical approval holds and restaurant code were preserved.

## Implemented and verified

- Persistent WAITING_QUOTA records provider, task/mission, confirmed machine error, last attempt, next eligible check, check count, availability and validated checkpoint/receipt. Legacy human holds are not automatically enrolled.
- Automatic resume is authorized at creation; its binding includes the definition, original start time, task/retry scope, runner safety code and validated files. Unknown in-flight work, changed scope/files, pause, WAITING_APPROVAL, CANCELLED and STOPPED never auto-resume. Original duration, invocation, retry/failure and spending policies are not reset.
- Explicit reset/Retry-After fields are used as lower bounds. A 15-minute global minimum limits requests; unknown recovery uses bounded exponential backoff up to 6 hours and at most eight checks per provider/store. No natural-language reset schedule is inferred.
- Auth/login status is not a capacity signal. Only an actual successful structured provider response confirms current availability. Minimal real probes require prior mission authorization, count as invocations and capture usage/duration. No hard cross-provider dollar cap is claimed.
- launchd one-shot worker uses the same writer lock, reconciles validated intermediate phases and persists probe outcomes atomically before further dispatch. A duplicate tick does not replay calls. Activation has separate explicit controls.

## Real versus simulated

Successful demo mission: b6b9f5999698. A parent process persisted WAITING_QUOTA; a separate Python worker reopened SQLite and automatically performed one REAL read-only Codex CLI availability request, one REAL Codex task and one REAL fresh Codex review. External pytest/HTTP/JS checks passed and mission became COMPLETED. A second worker, and an additional final-code worker, retained four total recorded attempts: one synthetic Claude limit plus three actual Codex CLI requests. No prompts/results were manually copied. Resource budgets remained 7200 seconds / 6 invocations / 0 retries, including the probe.

**Both initial quota errors, reset metadata and eligibility-time advancement were controlled simulations. No actual provider reset was observed. No new Claude request was made to exhaust its quota.** The API requests and external checks after eligibility were real; same-provider independent-context review is explicitly identified.

An earlier demo correctly stopped in WAITING_APPROVAL because its read-only review prompt prohibited the shell commands needed for file inspection. It remains held; a new bounded demo corrected that task scope instead of clearing its approval. The final activation teardown controller was adjusted after the live run to handle PATH changes and prevent uninstall of a still-loaded job. Runner/quota/probe logic and scheduler.tick are byte/AST-identical to the live run; those controller changes were tested with fake HOME and mocked launchctl. Code hashes/provenance are recorded in recovery-evidence.json.

## Tests and configuration

- `python3 -m unittest discover -s tools/agent-runner -p 'test_*.py' -q`: 63 tests pass (36 existing + 27 quota/scheduler tests). Coverage includes immediate takeover, both exhausted, reset/backoff, sleep/wake logical-time jumps, scope/deadline/failure limits, human holds, unknown children, writer conflicts, paid-probe invocation accounting, atomic probe-result crash recovery, interrupted handoff replay and validated partial checkpoint preservation without duplicate commits/calls.
- Existing OS-process-death checkpoint tests remain included. New recovery faults use controlled adapters; physical computer sleep/reboot and live launchd startup were not exercised.
- Existing application suite: 22 passed; one existing Starlette/httpx deprecation warning. Real-process loopback HTTP acceptance with restart passed; pip check passed. Browser/mobile testing is not claimed.
- Generated launchagent.plist passes `plutil -lint`; fixed arguments/round-trip/activation guards are tested. Install/enable/disable/uninstall tests use fake HOME and mocked launchctl, not the user's LaunchAgents directory.
- Actual scheduler status confirms `installed: false`, `loaded: false`. No persistent scheduler was installed, enabled or bootstrapped. Separate user authorization is required before either installation or activation.

## Operator locations and limits

Default DB: .agent-runner/state.sqlite. Successful demo: .agent-runner/demo-verified/state.sqlite. Private logs: .agent-runner/logs/scheduler.out.log and scheduler.err.log; events/usage remain in SQLite and are readable through scheduler logs/report. Earlier failed demo and all snapshots remain intact and ignored by Git.

Start a predefined opted-in mission with quota-review.json after preparing its reviewed .venv. Generate/review the LaunchAgent, then obtain separate authorization before install/enable. Short original deadlines may expire before the first 15-minute check; the runner intentionally does not extend them. Check exhaustion, unknown probe outcomes, changed code/scope and unavailable authentication require operator inspection rather than endless retries. Subscription billing and precise live reset detection remain unavailable from the observed CLI outputs.
