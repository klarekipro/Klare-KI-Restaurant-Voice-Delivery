# Current state — Mission 09

Branch: `fix/unattended-execution-timeout`; worktree: `/Users/admin/Projects/restaurant-timeout-recovery`.
Source: `5d06429b8b71c58266f58fa5fc03ddf634ad7264` plus local queue patch `784e23b`.
Validated implementation: `5aa4a88f5def49ee0d004f37119c7181d5eb78cd`.
Resolve final handoff SHA with `git rev-parse HEAD`; verify remote branch before takeover.
PR base: `feat/automatic-quota-resume`. Mission 09 authorizes a separate Draft PR, not merge or deployment.

Read `outputs/codex/mission-09/REPORT.md`, `evidence.json` and the timeout section of `tools/agent-runner/README.md`.
92 runner tests passed. Real isolated Claude timeout, Codex continuation and Claude review completed in mission
`a626518cbb1e`; duplicate drive created zero attempts. Earlier synthetic-fixture run `764e24a6287d` remains held
because compile generated unignored files. Neither record was rewritten to hide that failure.

Original night mission `86907825eb6d` remains WAITING_APPROVAL. PID/PGID 97481 are absent; 102 file hashes and all
mission records match the private read-only backup. No night mission resume, limit reset or job modification occurred.
This code is published for review only; the installed scheduler still points at its previous runner.

New missions may set `invocation_seconds` independently from total `max_seconds`; timeout recovery defaults to hold.
Only trusted, explicitly authorized local repeat-safe missions with external checkpoint checks may opt into checkpoint
continuation. Unknown execution outcomes and external side effects must not replay automatically.

Next: review the PR, especially process-group/timeout recovery assumptions. Any rollout to the active scheduler or
new recovery of the night mission must preserve its hold and original budgets; do not silently bind old code authorizations.
Long-duration production-like endurance, detached-process detection and night-task internal Claude actions remain unverified.

---

The following is historical Mission 06/08 context, not the current scheduler installation claim.

# Current state — Mission 06

Branch: feat/automatic-quota-resume. Worktree: /Users/admin/Projects/restaurant-quota-resume. Base PR5: 8471c4d5215b80cb260a546d339291afe727630e. Resolve final SHA with git rev-parse HEAD and verify remote/status before work. No merge/deployment approval.

Read tools/agent-runner/README.md and outputs/codex/mission-06/VALIDATION.md. WAITING_QUOTA is distinct from WAITING_APPROVAL. New missions must opt into auto_resume_quota and separately authorize any billable availability probe. Original deadlines and invocation/failure controls include waiting and probes.

Successful demo b6b9f5999698 is COMPLETED in .agent-runner/demo-verified/state.sqlite: controlled synthetic quota/reset/time, then three real Codex CLI requests (probe/work/fresh review), external validation, separate worker restart and no duplicated calls. Earlier scope-conflicting demo remains WAITING_APPROVAL in .agent-runner/demo/state.sqlite. Do not clear it automatically. No live quota reset or new Claude call was observed.

LaunchAgent generated in outputs/codex/mission-06/launchagent.plist and private .agent-runner/launchagent.plist; plutil lint passed. Actual status: NOT installed and NOT loaded. Do not install or enable it without separate user authorization. Logs/state locations and explicit install/enable/disable/uninstall commands are in README.

Checks: 63 runner tests; 22 application tests; HTTP acceptance/restart and pip check passed. Existing Starlette/httpx warning remains. Physical sleep/login launchd behavior and browser/mobile acceptance are unverified. DBs, provider auth, snapshots and logs are intentionally ignored; no application source was changed.

Next: independent scheduler security/recovery review, then obtain separate user approval if persistent activation is desired. Reproduce the controlled demo with a new private store; do not reset an old mission budget or claim simulated recovery as a live provider reset. Preserve all historical worktrees/holds.


Mission 08 enrollment preparation: the active local runner has a minimal tested deferred enqueue extension on fix/deferred-mission-queue, based on pinned 5d06429. Mission input: brief/missions/mission-08-demo-readiness.json. Registration uses enqueue --not-before 2026-11-02T02:00:00+01:00 in the active .agent-runner/state.sqlite, with no immediate AI call and no synthetic quota signal. Limits: six invocations, one retry, four consecutive failures, 86400 seconds from enrollment. Source application is pinned to 5d06429; validated results remain on a dedicated runner/<id> worktree branch. Mission ID, actual registration status and schedule are authoritative in SQLite; no publication, new dependency, deployment, merge or browser activation is authorized by this queue job.
