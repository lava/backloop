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
from pathlib import Path

# Add src to path to import reviewer modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from reviewer.review_manager import ReviewManager
from reviewer.models import Comment, ReviewApproved
from reviewer.settings import settings


async def main() -> None:
    """Main test function."""
    if settings.debug:
        print("[DEBUG] Running in debug mode")
        print(f"[DEBUG] Debug setting: {settings.debug}")
    
    # Initialize review manager
    review_manager = ReviewManager()
    
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
        elif isinstance(result, Comment):
            comment_count += 1
            print(f"\n📝 Comment #{comment_count}")
            print(f"   File: {result.file_path}")
            print(f"   Line: {result.line_number} ({result.side} side)")
            print(f"   Author: {result.author}")
            print(f"   Content: {result.content}")
            print("-" * 60)
        else:
            print(f"\n⚠️  Unexpected result type: {type(result)}")
    
    print("\n✅ Test completed successfully!")


if __name__ == "__main__":
    if settings.debug:
        print(f"[DEBUG] Starting test script with BACKLOOP_CI_DEBUG={settings.debug}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(0)