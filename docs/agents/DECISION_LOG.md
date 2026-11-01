# Decisions

- Mission 03 explicitly authorizes local MVP implementation and publication, superseding the earlier bootstrap-only restriction. Brief remains unchanged.
- Base hardening on PR #2 source f73b97b76f7ab0694aa1fbb0a8f87c0d73e260bb in a separate worktree; target PR base feat/mvp-restaurant-voice.
- Keep existing dependency surface. requirements-local.lock records the actual tested environment; it is a snapshot for this platform/Python, not a universal lock.
- Generate persistent 0600 per-database signing secret instead of public fallback; existing sessions must log in again. Exclude key and SQLite sidecars from Git.
- Snapshot contacts per order and backfill existing records on startup. Later CRM changes cannot redirect an existing delivery. Migration cannot reconstruct historical addresses already overwritten before this change.
- Use per-actor persisted idempotency key for simulator requests. Browser retains one key for page lifetime; open a new simulator page for a new order. Payload changes under a successful key return 409. Clients without a key are not deduplicated.
- Count delivered revenue by delivery timestamp in half-open Europe/Berlin calendar windows; average delivered ticket divides by delivered count. Include inactive couriers in history.
- SQLite BEGIN IMMEDIATE serializes transitions and their audit events. Do not infer distributed/concurrent-load readiness from local tests.

- Mission 04: runner is a separate stdlib component under tools/agent-runner, based on PR3. macOS backend only, fail closed elsewhere. Native Codex profiles avoid incompatible nested Seatbelt. Source: https://learn.chatgpt.com/docs/config-file/config-reference.
- Provider statements are task-scoped evidence; runner requires schema and external checks. Review completion is not product readiness. New dependencies/configuration and uncertain dirty outcomes require approval.
- Partial real repair stopped at machine API429 and is preserved, not published. Historical approval holds are never silently cleared by upgraded code.

- Mission 05: preserve the original held tree; import recorded API429/task/bytes into a new authorized worktree. Safety-checked incomplete checkpoints and verified completed tasks have distinct classifications. No unvalidated checkpoint commits.
- Normalized outcomes, content-bound receipts, atomic unique handoffs and committed-tree identity support replay across interrupted handoffs. Unknown process outcomes still hold.
- Explicit safety checks may differ from final completion checks; final acceptance and independent-context review remain mandatory. Same-provider review fallback is opt-in and logged.
- A failed bounded mission is terminal. A new explicitly authorized follow-up forwards structured findings, preserving source records and inherited caps; it cannot silently clear an approval hold.
