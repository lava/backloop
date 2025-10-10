# MCP Web Server Not Starting - Investigation

## Problem
The MCP server's web server is not starting. When calling `startreview()`, a review URL is returned (e.g., http://127.0.0.1:42101/review/69a5517e) but the connection is refused - the port is not listening.

## Error Message
From debug logs with `BACKLOOP_DEBUG=1`:
```
[DEBUG] Background thread starting uvicorn on port <port>
[ERROR] Failed to start uvicorn: There is no current event loop in thread 'Thread-4 (run_server)'.
```

## When It Broke
- **Commit**: 5780164 ("Fix tests and various glitches")
- **Date**: October 10, 2025 at 04:42
- **What changed**: Added `nest-asyncio` dependency and called `nest_asyncio.apply()` in `src/backloop/__init__.py`

## Root Cause Investigation

### Timeline of Changes

1. **Original working code** (before refactoring):
   - In `ReviewManager.start_web_server()`:
   ```python
   def run_server() -> None:
       uvicorn.run(self._main_app, host="127.0.0.1", port=port, log_level="warning")
   ```
   - Used `host/port` parameters
   - Worked fine in background thread

2. **Commit c4bb14d** (Oct 4, 2025 - "Fix MCP server after refactoring"):
   - Changed to use file descriptor approach:
   ```python
   def run_server() -> None:
       uvicorn.run(app, fd=sock.fileno())
   ```
   - This worked initially

3. **Commit 5780164** (Oct 10, 2025 - TODAY):
   - Added `nest-asyncio` to handle pytest-asyncio event loop warnings
   - Added to `src/backloop/__init__.py`:
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```
   - This globally patches asyncio to allow nested event loops
   - **This broke the MCP web server startup**

### Why nest-asyncio Broke It

`nest_asyncio.apply()` globally patches asyncio's event loop behavior. When uvicorn tries to run in a background thread:
- The `fd=` parameter requires an event loop to exist in the thread
- The nest-asyncio patches interfere with uvicorn's event loop creation
- Result: "There is no current event loop in thread" error

## Attempted Fixes (Still Not Working)

### Fix Attempt #1: Create Event Loop in Thread
```python
def run_server() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run(app, fd=sock.fileno())
```
**Status**: Did not work

### Fix Attempt #2: Switch Back to host/port + Event Loop
```python
sock, port = get_random_port()
sock.close()  # Close socket, uvicorn will reopen it

def run_server() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
```
**Status**: Did not work (still getting the same error after restart)

## Files Modified in Attempted Fixes
- `src/backloop/utils/common.py` - Added `debug_write()` function with BACKLOOP_DEBUG env check
- `src/backloop/file_watcher.py` - Use `debug_write()` from utils
- `src/backloop/server.py` - Use `debug_write()` from utils
- `src/backloop/mcp/server.py` - Added debug logging + event loop creation + host/port approach

## Next Steps to Investigate

1. **Test if removing nest-asyncio fixes it**
   - Comment out `nest_asyncio.apply()` in `src/backloop/__init__.py`
   - Restart MCP server and test

2. **Check if nest-asyncio can be scoped differently**
   - Maybe only apply it for tests, not for production code
   - Move `nest_asyncio.apply()` to test fixtures instead of package init

3. **Alternative: Run uvicorn differently**
   - Use uvicorn's Config/Server classes directly instead of uvicorn.run()
   - This gives more control over event loop creation

4. **Check uvicorn compatibility with nest-asyncio**
   - Search for known issues between uvicorn and nest-asyncio
   - Check if there's a different way to handle nested event loops

## Working Theory

The nest-asyncio patches are preventing uvicorn from starting properly in the background thread, even when we explicitly create an event loop. The patches may be interfering with uvicorn's internal event loop management.

## Key Question

Why was nest-asyncio needed? According to commit 5780164:
> Allow nested event loops so pytest-asyncio can coexist with other runners.

Can we achieve the same goal (fixing pytest-asyncio warnings) without breaking the MCP server?
