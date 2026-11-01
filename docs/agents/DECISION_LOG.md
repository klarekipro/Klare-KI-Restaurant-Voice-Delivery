# Decisions

- Mission 03 explicitly authorizes local MVP implementation and publication, superseding the earlier bootstrap-only restriction. Brief remains unchanged.
- Base hardening on PR #2 source f73b97b76f7ab0694aa1fbb0a8f87c0d73e260bb in a separate worktree; target PR base feat/mvp-restaurant-voice.
- Keep existing dependency surface. requirements-local.lock records the actual tested environment; it is a snapshot for this platform/Python, not a universal lock.
- Generate persistent 0600 per-database signing secret instead of public fallback; existing sessions must log in again. Exclude key and SQLite sidecars from Git.
- Snapshot contacts per order and backfill existing records on startup. Later CRM changes cannot redirect an existing delivery. Migration cannot reconstruct historical addresses already overwritten before this change.
- Use per-actor persisted idempotency key for simulator requests. Browser retains one key for page lifetime; open a new simulator page for a new order. Payload changes under a successful key return 409. Clients without a key are not deduplicated.
- Count delivered revenue by delivery timestamp in half-open Europe/Berlin calendar windows; average delivered ticket divides by delivered count. Include inactive couriers in history.
- SQLite BEGIN IMMEDIATE serializes transitions and their audit events. Do not infer distributed/concurrent-load readiness from local tests.
