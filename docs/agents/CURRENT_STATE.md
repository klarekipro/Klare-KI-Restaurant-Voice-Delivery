# Current state — Mission 06

Branch: feat/automatic-quota-resume. Worktree: /Users/admin/Projects/restaurant-quota-resume. Base PR5: 8471c4d5215b80cb260a546d339291afe727630e. Resolve final SHA with git rev-parse HEAD and verify remote/status before work. No merge/deployment approval.

Read tools/agent-runner/README.md and outputs/codex/mission-06/VALIDATION.md. WAITING_QUOTA is distinct from WAITING_APPROVAL. New missions must opt into auto_resume_quota and separately authorize any billable availability probe. Original deadlines and invocation/failure controls include waiting and probes.

Successful demo b6b9f5999698 is COMPLETED in .agent-runner/demo-verified/state.sqlite: controlled synthetic quota/reset/time, then three real Codex CLI requests (probe/work/fresh review), external validation, separate worker restart and no duplicated calls. Earlier scope-conflicting demo remains WAITING_APPROVAL in .agent-runner/demo/state.sqlite. Do not clear it automatically. No live quota reset or new Claude call was observed.

LaunchAgent generated in outputs/codex/mission-06/launchagent.plist and private .agent-runner/launchagent.plist; plutil lint passed. Actual status: NOT installed and NOT loaded. Do not install or enable it without separate user authorization. Logs/state locations and explicit install/enable/disable/uninstall commands are in README.

Checks: 63 runner tests; 22 application tests; HTTP acceptance/restart and pip check passed. Existing Starlette/httpx warning remains. Physical sleep/login launchd behavior and browser/mobile acceptance are unverified. DBs, provider auth, snapshots and logs are intentionally ignored; no application source was changed.

Next: independent scheduler security/recovery review, then obtain separate user approval if persistent activation is desired. Reproduce the controlled demo with a new private store; do not reset an old mission budget or claim simulated recovery as a live provider reset. Preserve all historical worktrees/holds.
