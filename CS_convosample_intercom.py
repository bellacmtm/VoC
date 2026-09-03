"""
VoC Project — Step 2: Pull sample conversations from Intercom
----------------------------------------------------------------
What this does:
  1. Connects to the Intercom API using your access token
  2. SEARCHES for conversations that are CLOSED (not open/snoozed) —
     open conversations aren't finished yet, so they're not useful
     for reporting on how a conversation actually went
  3. For each one, fetches the FULL conversation (with all messages)
  4. Skips conversations that:
       - have no real messages at all (empty/junk conversations)
       - match a topic on the Ops-provided exclusion list
       - are Free Spins related in any way (broader than just the
         exact "FS - Granted" / "FS - welcome offer" list entries,
         per direct instruction to exclude all Free Spins content)
  5. Saves everything that's left to a local JSON file

Before running:
  1. Install the requests library:
       pip install requests --break-system-packages
       (or just: pip install requests)

  2. Set your Intercom token as an environment variable instead of
     pasting it into this file. This keeps it out of any code you
     might commit to a repo later.

     On Windows (PowerShell):
       $env:INTERCOM_ACCESS_TOKEN="your_token_here"

  3. Run the script:
       python pull_sample_conversations.py
"""

import os
import json
import time
import requests

# ---- Config ----
ACCESS_TOKEN = os.environ.get("INTERCOM_ACCESS_TOKEN")
INTERCOM_VERSION = "2.11"  # stable, widely supported version
SAMPLE_SIZE = 10  # how many qualifying conversations we want to end up with
OUTPUT_FILE = "sample_conversations.json"

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Intercom-Version": INTERCOM_VERSION,
}

# Topics to exclude, provided by Head of Ops. Matched exactly
# (case-insensitive) against each conversation's topic list.
EXCLUDED_TOPICS = {
    "3rd party contact",
    "account reopening",
    "bonus bot circumvention",
    "bonus bot fs",
    "cc- removal",
    "change of details",
    "deposit missing - within timeframe",
    "deposit pending - within timeframe",
    "fs - granted",
    "fs - welcome offer",
    "no response",
    "se email error query",
    "se email error re-open",
    "self exclusion",
    "take a break",
    "testing",
    "wd - within timeframe",
    "welcome offer - granted",
}

# Free Spins content should be excluded entirely, in any form —
# broader than just the exact "FS - ..." entries above.
FREE_SPINS_KEYWORDS = ["free spin", "fs -", "fs_"]


def check_token():
    if not ACCESS_TOKEN:
        raise SystemExit(
            "No token found. Set the INTERCOM_ACCESS_TOKEN environment "
            "variable before running this script (see the notes at the "
            "top of this file)."
        )


def search_closed_conversations(limit=SAMPLE_SIZE):
    """
    Ask Intercom directly for CLOSED conversations only, most recently
    updated first. This filters on Intercom's side, so we're not wasting
    time downloading a bunch of still-open chats we don't want.
    """
    url = f"{BASE_URL}/conversations/search"
    body = {
        "query": {
            "field": "state",
            "operator": "=",
            "value": "closed",
        },
        "pagination": {"per_page": limit},
    }
    response = requests.post(url, headers=HEADERS, json=body)
    response.raise_for_status()
    data = response.json()
    return data.get("conversations", [])


def get_full_conversation(conversation_id):
    """Get one conversation with all its messages (conversation_parts)."""
    url = f"{BASE_URL}/conversations/{conversation_id}"
    params = {"display_as": "plaintext"}  # returns clean text, not HTML
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def has_real_messages(full_conversation):
    """
    Check whether this conversation has at least one actual typed message
    (from anyone — bot, agent, or player). Skips empty/junk conversations
    that are closed but never had any real content.
    """
    parts = full_conversation.get("conversation_parts", {}).get("conversation_parts", [])
    for part in parts:
        if part.get("part_type") == "comment" and part.get("body"):
            return True
    return False


def get_topics(full_conversation):
    """Pull out the list of topic names attached to this conversation."""
    topics = full_conversation.get("topics", {}).get("topics", [])
    return [t["name"] for t in topics if t.get("name")]


def is_excluded_topic(topics):
    """
    Check a conversation's topics against the Ops exclusion list, plus a
    broader Free Spins catch-all (per instruction to exclude all Free
    Spins content, not just the exact topic names on the list).
    """
    for topic in topics:
        topic_lower = topic.lower().strip()

        if topic_lower in EXCLUDED_TOPICS:
            return True

        if any(keyword in topic_lower for keyword in FREE_SPINS_KEYWORDS):
            return True

    return False


def main():
    check_token()

    print(f"Searching Intercom for closed conversations...")
    # Ask for a bigger batch than we need, since exclusion filters below
    # will remove some of them.
    candidates = search_closed_conversations(limit=SAMPLE_SIZE * 4)
    print(f"Found {len(candidates)} closed conversations to check.")

    qualifying_conversations = []
    for i, convo in enumerate(candidates, start=1):
        if len(qualifying_conversations) >= SAMPLE_SIZE:
            break  # we have enough, stop early

        convo_id = convo["id"]
        print(f"  [{i}/{len(candidates)}] Checking conversation {convo_id}...")

        try:
            full = get_full_conversation(convo_id)
        except requests.HTTPError as e:
            print(f"    Skipped {convo_id} due to error: {e}")
            continue

        if not has_real_messages(full):
            print(f"    Skipped — no real messages (empty conversation).")
            continue

        topics = get_topics(full)
        if is_excluded_topic(topics):
            print(f"    Skipped — matched an excluded topic ({topics}).")
            continue

        qualifying_conversations.append(full)
        print(f"    Kept.")

        time.sleep(0.3)  # be polite to the API, avoid rate limits

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(qualifying_conversations, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved {len(qualifying_conversations)} qualifying conversations to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()