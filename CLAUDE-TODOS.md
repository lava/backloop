## High Priority

- [x] **Consolidate configuration systems** - Merge duplicate `Config` and `Settings` classes into a single unified configuration system with consistent naming (`src/backloop/config.py`, `src/backloop/utils/settings.py`). Currently using both `REVIEWER_` and `LOOPBACK_CI_` prefixes inconsistently. ✅ Completed: Now using unified Settings class with BACKLOOP_* prefix and backward compatibility for legacy prefixes.

- [ ] **Add proper automated tests** - Create comprehensive unit and integration test suite for core functionality (git service, comment service, review manager, API endpoints). Currently only manual test scripts exist.

## Medium Priority

- [x] Fix comment queue to track per-review ownership and return review IDs from await_comments (prevents dequeuing from wrong session).
- [ ] Scope EventManager deliveries so only subscribers for a review receive its events.
- [ ] Recalculate remaining queue positions after comment deletions to keep ordering accurate.
- [ ] Harden /api/edit path handling to block edits outside the repository root.
