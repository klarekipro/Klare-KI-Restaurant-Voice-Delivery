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

Single writer enforced by state-directory OS lock, unique mission worktrees and sequential execution (`max_concurrent=1`). Pause/stop terminate the active process group and persist an uncertain outcome. Stop is terminal; pause during execution requires inspection and explicit recovery approval. Recovery of uncertain in-flight execution holds for inspection rather than repeating possibly completed actions. No automatic approval grant: WAITING_APPROVAL cannot be cleared by resume. After inspecting a clean preserved worktree, an operator can run `approve <mission-id> --approval-note "reason"`, then `resume <mission-id>`. Live recorded PIDs block approval. Commands without an ID target the latest mission. Inspect/terminate an orphan process and preserve the worktree before creating a new explicitly authorized mission.

Claude uses a probed outer Seatbelt sandbox; Codex uses its probed native named filesystem profile to avoid nested Seatbelt failures. Read access is limited to system/runtime paths, repository Git metadata, the task worktree and private scratch; writes are limited to task/scratch. Environment is allowlisted; clean provider HOME receives only a copied Codex auth file. Claude receives only its existing OAuth access token from the named Claude Code Keychain service, without logging it. No production credentials are inherited. MCP/user settings are excluded. Claude project roles remain available. Edits require explicit `allow_edits: true` in the trusted mission definition. Out-of-scope paths, symlinks, possible keys, existing regression-test changes and failed validation with dirty worktrees hold for inspection. Authorized app/docs/new-test edits run only through sandboxed allowlisted checks before a local commit (hooks/signing disabled). No new dependency installation, automatic publication or merge. Validators use a clean environment and allow loopback networking for the existing acceptance server. No push/merge/deployment is implemented.

Both limits and generic failures are bounded. Only machine error codes classify confirmed provider limits; prose claiming a limit is unconfirmed and holds. Retry times remain unknown unless available; availability is persisted. No cross-provider hard dollar cap is claimed: mission monetary-cap requests fail closed, Claude additionally gets its native $1 invocation budget. Duration/invocation/retry/consecutive-failure limits remain primary controls. Raw errors/usage are retained locally; reporting requires manual redaction before sharing.

Authentication may fail in the clean HOME; runner must hold or fail rather than enabling broad HOME access, unrestricted permissions or credential environment inheritance. Review verification evidence before using this prototype autonomously.

Native Codex profile reference: https://learn.chatgpt.com/docs/config-file/config-reference (`permissions.<name>.filesystem`, `default_permissions`). Scope is verified with a negative filesystem probe before each invocation. Tests of mocked outcomes do not establish live provider-limit behavior.

For the bounded demo repair, prepare the reviewed existing test dependencies with `python3 -m venv .venv && .venv/bin/pip install -r requirements-local.lock`, then `python3 tools/agent-runner/runner.py start tools/agent-runner/fix-demo.json`. The Python path is relative to the operator working directory; use a reviewed project venv, never an untrusted executable. This mission authorizes only the requested template repair.


## Validated takeover and recovery (Mission 05)

Checkpoint stages are PRESERVED → VALIDATED → COMMITTED → HANDED_OFF. Incomplete work is never labelled complete. Before commit/handoff, scope and key checks, a full content fingerprint and controlled external checks must pass. `checkpoint_checks` selects explicitly trusted safety checks (default: all mission checks); completion still requires all `checks` plus a fresh review and matching validation receipt. The shipped historical recovery uses pytest + HTTP acceptance as safety checks, and adds the simulator retry behavior check for completion. A failed safety check or changed fingerprint holds without committing. Missing provider final JSON is not evidence of completed work.

SQLite stores normalized outcomes before scheduling. Checkpoint replay recognizes an already-created Git commit using its parent, marker and full committed-content digest; task/handoff creation is atomic and unique per attempt. Unknown in-flight executions still hold; no PID or approval protections are removed. A test kills a real runner process with os._exit between Git commit and SQLite recording and verifies one commit, no lost bytes and no repeated provider action after restart.

To recover the historical held mission, explicitly authorize a separate import; the original worktree and approval hold remain untouched:

```
python3 tools/agent-runner/runner.py recover-held 92bd71a914ab \
  --from-state /absolute/path/to/original/.agent-runner/state.sqlite \
  --python /absolute/path/to/reviewed/.venv/bin/python \
  --approval-note "Explicit recovery authorization and scope"
```

No manual prompt/report copying is required: SQLite records, original bytes and machine API429 evidence are imported automatically. Repeated imports return the same new mission; an incomplete construction holds rather than creating a duplicate. Inherited duration/invocation/retry caps are preserved. A new follow-up after a review rejects a result requires explicit authorization: `followup <failed-mission-id> --approval-note "authority and bounded scope"`. It forwards structured findings automatically and does not reopen or reset the failed mission. It cannot clear WAITING_APPROVAL.

If authorized with `review_fallback: true`, an available provider may perform a fresh independent-context review when the other provider is unavailable. This is logged as same-provider review, never described as cross-provider review. External checks remain mandatory. Browser/mobile testing is not claimed by the Node DOM-stub check.

## Quota waiting and unattended continuation (Mission 06)

New missions opt in with `auto_resume_quota: true`. `quota_probe_authorized: true` separately authorizes minimal real availability requests if no authoritative success signal exists. `quota-review.json` is a predefined read-only example; prepare the existing project `.venv` first. It has an explicit 24-hour wall-clock budget and six total invocations. Waiting, sleep and probes do not reset that budget. Short original mission deadlines can expire before quota recovery.

```
python3 tools/agent-runner/runner.py start tools/agent-runner/quota-review.json
python3 tools/agent-runner/runner.py quota status
python3 tools/agent-runner/runner.py quota next-check
python3 tools/agent-runner/runner.py scheduler status
python3 tools/agent-runner/runner.py scheduler logs
python3 tools/agent-runner/runner.py scheduler tick
```

`WAITING_QUOTA` is distinct from FAILED and WAITING_APPROVAL. SQLite records task/provider, confirmed machine error, last attempt, next eligible check, check count, availability and validated checkpoint/receipt. Authentication, network errors and approval requests are not quota signals. Reliable machine reset timestamps/Retry-After are honored as lower bounds; no natural-language reset schedules are inferred. Without reset metadata, checks back off from 15 minutes to 6 hours, globally at most four checks/hour/provider and eight checks per provider signal store. After that limit the status shows `check_limit_reached`; no silent counter reset occurs.

Login status is not a quota-capacity signal. A successful structured provider response can prove current availability without another probe. Otherwise only a preauthorized narrowly scoped probe may run; Claude has no tools and Codex has read-only project access. Every probe is a persisted invocation with exit/usage/duration and consumes the same mission budgets. Cross-provider dollar caps remain unsupported/fail-closed. A successful availability answer does not guarantee that a later task will not hit another limit.

Automatic resume binds the original definition, start time, task prompt/retry counter, runner safety-code digest and validated file contents. Changed scope, unknown in-flight execution, dirty unvalidated work or a human hold prevents scheduling. CANCELLED/STOPPED/paused missions do not resume. Validated intermediate handoff/finalization phases can be reconciled after a crash. Probe results and recovery signals are atomic, so a restart after a successful probe does not bill the same check again. One writer lock covers scheduler and manual execution; an active provider is never interrupted merely because another recovers.

### LaunchAgent configuration and activation

Generate and inspect without activating anything:

```
python3 tools/agent-runner/runner.py scheduler generate
plutil -lint .agent-runner/launchagent.plist
```

The per-user job is `com.klareki.agent-runner`, with a 300-second one-shot interval, RunAtLoad after login, fixed Python arguments and no mission-provided shell commands. It needs no server or root. On wake the next worker evaluates persisted eligibility once, not a backlog of requests. Physical login/sleep integration is not verified until separately authorized activation.

**Do not execute the following until the user separately approves persistent activation.** The note is recorded; do not put secrets in it.

```
python3 tools/agent-runner/runner.py scheduler install --authorize-activation "User approval reference"
python3 tools/agent-runner/runner.py scheduler enable --authorize-activation "User approval reference"
python3 tools/agent-runner/runner.py scheduler disable --authorize-activation "User approval reference"
python3 tools/agent-runner/runner.py scheduler uninstall --authorize-activation "User approval reference"
```

Install only copies the exact reviewed configuration to `~/Library/LaunchAgents/com.klareki.agent-runner.plist`; it is itself a persistent change (including future login). Enable uses the current user's launchctl GUI domain. Unknown existing configurations are never overwritten or removed. Editing/moving the runner or mission can invalidate waiting authorizations; do not silently rebind them.

Default private state: `.agent-runner/state.sqlite`; readable events: SQLite `events` / `scheduler logs`; launchd stdout/stderr: `.agent-runner/logs/scheduler.{out,err}.log`. Use `--state /absolute/path` consistently before commands for another store. Preserve these directories across restarts; do not commit databases, credentials or snapshots.

### Reproducible real-CLI recovery demo

```
python3 tools/agent-runner/demo_quota.py run --state .agent-runner/demo-new/state.sqlite --python /absolute/path/to/reviewed/.venv/bin/python
```

This uses a new private store, controlled synthetic 429/reset metadata and simulated eligibility time, then starts a separate one-shot worker with **real Codex CLI** availability/work/review requests plus external checks. It does not install launchd, exhaust real quota, alter the system clock or claim live reset detection. A duplicate worker verifies that completed work is not repeated. See `outputs/codex/mission-06/VALIDATION.md` for measured coverage.

Teardown uses the last reviewed installed bytes, so a changed terminal PATH does not prevent disable/uninstall. Uninstall refuses to remove the configuration while launchctl still reports the job loaded. Activation still requires a freshly reviewed exact configuration.


## Deferred enrollment (minimal Mission 08 extension)

`enqueue <mission-file> --not-before <timezone-aware ISO timestamp>` registers a mission/worktree in SQLite without calling any provider. This is a scheduling gate, not WAITING_QUOTA and not a quota reset claim. Scheduler status and quota next-check show pending scheduled work. The original duration starts at enrollment and includes the delay; no budgets are reset. A future Engine.step/resume cannot bypass not-before. After the time gate, normal provider selection and real quota handling apply. Pauses, holds, scope/code/branch changes, unknown work and expired budgets still prevent dispatch. The same writer lock and private SQLite store are used; no second runner/service is installed.
