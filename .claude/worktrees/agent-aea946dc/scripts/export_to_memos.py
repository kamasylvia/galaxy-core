#!/usr/bin/env python3
"""
Export task history to Memos
Usage: python scripts/export_to_memos.py <task_history_file>
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MEMOS_URL = os.getenv("MEMOS_URL", "")
MEMOS_TOKEN = os.getenv("MEMOS_TOKEN", "")


def create_memos_note(content: str, tags: list[str] | None = None):
    """Create a new note in Memos"""
    if not MEMOS_URL or not MEMOS_TOKEN:
        print("Error: MEMOS_URL or MEMOS_TOKEN not configured in .env")
        return False

    url = f"{MEMOS_URL}/api/v1/memos"

    data = {
        "content": content,
        "visibility": "PRIVATE",
    }

    if tags:
        data["tags"] = tags

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MEMOS_TOKEN}",
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                result = json.loads(response.read().decode("utf-8"))
                print(f"Successfully created Memos note with ID: {result.get('id')}")
                return True
            else:
                print(f"Failed to create note. Status: {response.status}")
                return False

    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(f"Response: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        # Default to the task history file
        task_history_file = Path("docs/task_history_2026-03-08.md")
    else:
        task_history_file = Path(sys.argv[1])

    if not task_history_file.exists():
        print(f"Error: File not found: {task_history_file}")
        sys.exit(1)

    # Read the task history content
    content = task_history_file.read_text(encoding="utf-8")

    # Add task-history tag if not present
    if "#task-history" not in content:
        content += "\n\n#task-history"

    print(f"Exporting {task_history_file} to Memos...")
    print(f"Memos URL: {MEMOS_URL}")

    success = create_memos_note(content, tags=["task-history"])

    if success:
        print("Export completed successfully!")
        sys.exit(0)
    else:
        print("Export failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
