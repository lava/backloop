# Refactoring Tasks

## 1. Remove Mock Routes and Consolidate Mock Functionality ✅
- [x] Remove `/mock` and `/mock-data.js` routes from `server.py`
- [x] Remove `/mock` and `/mock-data.js` routes from `review_manager.py:create_dynamic_router()`
- [x] Remove `mock.html` and `mock-data.js` files if they exist (files did not exist)
- [x] Ensure mock functionality is fully handled by the `mock` parameter in `/api/diff` endpoints
- [x] Update any documentation or tests that reference the removed mock routes (no documentation/tests found referencing these routes)

## 2. API Response Consistency ✅
- [x] Create `src/loopback/responses.py` with standardized response models
- [x] Define `SuccessResponse`, `ErrorResponse`, and `CommentResponse` models
- [x] Update all API endpoints to return consistent response formats
- [x] Replace dict returns with proper response models
- [x] Ensure all endpoints have proper response model type hints

## 3. Type Hint Improvements ✅
- [x] Add missing return type hints for async functions across all modules
- [x] Convert `Optional[X]` to `X | None` syntax (Python 3.10+)
- [x] Add type hints to function parameters that are missing them
- [x] Ensure all class methods have proper type hints
- [x] Run mypy to verify type correctness after changes

## 4. Simplify Event Management with asyncio.Queue ✅
- [x] Replace `_pending_comments: List[Comment]` with `asyncio.Queue[Comment]`
- [x] Remove manual thread-safe event loop callbacks in `ReviewManager`
- [x] Refactor `add_comment_to_queue()` to use queue.put()
- [x] Refactor `await_comments()` to use queue.get() with timeout
- [x] Simplify the event notification system between FastAPI and MCP threads

## 5. Improve Error Handling
- [ ] Create `src/loopback/exceptions.py` with custom exception classes
- [ ] Define exceptions: `ReviewNotFoundError`, `CommentNotFoundError`, `GitOperationError`
- [ ] Create centralized error handler middleware in `src/loopback/middleware.py`
- [ ] Update all modules to use custom exceptions instead of generic HTTPException
- [ ] Ensure consistent error response format across all endpoints