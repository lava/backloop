#!/usr/bin/env python3
"""Manual test script that simulates MCP server operation.

This script:
1. Starts a review session for changes since HEAD~1
2. Prints the review URL
3. Waits for comments and prints them
4. Continues until the review is approved
"""

import asyncio
import sys
import json
import time
from pathlib import Path
from typing import Optional

# Add project source and test helpers to the path for manual execution
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_support.review_manager import ReviewManager, PendingComment
from backloop.models import Comment, ReviewApproved
from backloop.config import settings
from backloop.event_manager import EventType


async def monitor_events(
    review_manager: ReviewManager, stop_event: asyncio.Event
) -> None:
    """Monitor events in the background and print them."""
    print("\n🔍 Starting event monitor...")
    last_event_id: Optional[str] = None

    while not stop_event.is_set():
        try:
            # Subscribe to events
            subscriber = await review_manager.event_manager.subscribe(last_event_id)

            # Wait for events with a short timeout
            events = await review_manager.event_manager.wait_for_events(
                subscriber, timeout=2.0
            )

            # Print any events received
            for event in events:
                print(f"\n📡 EVENT: {event.type.value}")
                print(f"   ID: {event.id}")
                print(f"   Data: {json.dumps(event.data, indent=6)}")
                print(f"   Review ID: {event.review_id}")
                print(
                    f"   Timestamp: {time.strftime('%H:%M:%S', time.localtime(event.timestamp))}"
                )
                last_event_id = event.id

            # Unsubscribe
            await review_manager.event_manager.unsubscribe(subscriber.id)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️  Event monitor error: {e}")
            await asyncio.sleep(1)


async def main() -> None:
    """Main test function."""
    if settings.debug:
        print("[DEBUG] Running in debug mode")
        print(f"[DEBUG] Debug setting: {settings.debug}")

    # Initialize review manager
    loop = asyncio.get_running_loop()
    review_manager = ReviewManager(loop)

    # Create a review session for changes since HEAD~1
    print("Starting review session for changes since HEAD~1...")
    review_session = review_manager.create_review_session(since="HEAD~1")

    # Start web server and get URL
    port = review_manager.start_web_server()
    review_url = f"http://127.0.0.1:{port}/review/{review_session.id}"

    print(f"\n✨ Review session started!")
    print(f"📎 Review URL: {review_url}")
    print(f"\nWaiting for review comments...")
    print("=" * 60)

    # Start event monitor in background
    stop_event = asyncio.Event()
    event_monitor_task = asyncio.create_task(monitor_events(review_manager, stop_event))

    comment_count = 0

    # Keep waiting for comments until review is approved
    while True:
        if settings.debug:
            print("[DEBUG] Calling await_comments...")

        result = await review_manager.await_comments()

        if settings.debug:
            print(f"[DEBUG] await_comments returned: {type(result).__name__}")

        if isinstance(result, ReviewApproved):
            print("\n🎉 REVIEW APPROVED!")
            print(f"Review {result.review_id} was approved at {result.timestamp}")
            print(f"Total comments received: {comment_count}")
            break
        elif isinstance(result, PendingComment):
            comment_count += 1
            print(f"\n📝 Comment #{comment_count}")
            print(f"   Review: {result.review_id}")
            print(f"   File: {result.comment.file_path}")
            print(f"   Line: {result.comment.line_number} ({result.comment.side} side)")
            print(f"   Author: {result.comment.author}")
            print(f"   Content: {result.comment.content}")
            print("-" * 60)
        else:
            print(f"\n⚠️  Unexpected result type: {type(result)}")

    # Stop event monitor
    stop_event.set()
    event_monitor_task.cancel()
    try:
        await event_monitor_task
    except asyncio.CancelledError:
        pass

    print("\n✅ Test completed successfully!")


if __name__ == "__main__":
    if settings.debug:
        print(f"[DEBUG] Starting test script with LOOPBACK_CI_DEBUG={settings.debug}")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(0)
