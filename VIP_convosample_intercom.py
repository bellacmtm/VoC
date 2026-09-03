import requests
import json
import os
import time

# Set your token as an environment variable before running this,
# so it's never typed directly into the script file.
# On Mac/Linux (terminal): export INTERCOM_TOKEN="your_token_here"
# On Windows (PowerShell): $env:INTERCOM_TOKEN="your_token_here"

TOKEN = os.environ.get("INTERCOM_TOKEN")

if not TOKEN:
    raise SystemExit("INTERCOM_TOKEN environment variable not set. See instructions above.")

# How many conversations you actually want for this test
SAMPLE_SIZE = 15

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}

def get_conversation_list(sample_size):
    """Step 1: get a small list of recent conversations (summary only)."""
    url = f"{BASE_URL}/conversations"
    params = {"per_page": sample_size}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("conversations", [])[:sample_size]

def get_conversation_detail(conversation_id):
    """Step 2: fetch the full thread (conversation_parts) for one conversation."""
    url = f"{BASE_URL}/conversations/{conversation_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def extract_messages(conversation_detail):
    """Pull out just the useful verbatim text, in order, from a full conversation object."""
    messages = []

    source = conversation_detail.get("source", {})
    if source.get("body"):
        messages.append({
            "author_type": source.get("author", {}).get("type"),
            "author_name": source.get("author", {}).get("name"),
            "body": source.get("body"),
        })

    parts = conversation_detail.get("conversation_parts", {}).get("conversation_parts", [])
    for part in parts:
        if part.get("body"):
            author = part.get("author", {})
            messages.append({
                "author_type": author.get("type"),
                "author_name": author.get("name"),
                "body": part.get("body"),
            })

    return messages

def main():
    print(f"Fetching a list of {SAMPLE_SIZE} conversations...")
    summaries = get_conversation_list(SAMPLE_SIZE)
    print(f"Got {len(summaries)} conversation summaries. Fetching full detail for each...")

    full_conversations = []
    for i, summary in enumerate(summaries, 1):
        conv_id = summary["id"]
        print(f"  [{i}/{len(summaries)}] fetching conversation {conv_id}")
        detail = get_conversation_detail(conv_id)

        full_conversations.append({
            "id": conv_id,
            "brand": detail.get("custom_attributes", {}).get("Brand"),
            "ai_title": detail.get("custom_attributes", {}).get("AI Title"),
            "language": detail.get("custom_attributes", {}).get("Language"),
            "created_at": detail.get("created_at"),
            "messages": extract_messages(detail),
        })

        time.sleep(0.3)  # be polite to the API, avoid rate limits

    with open("intercom_full_sample.json", "w") as f:
        json.dump(full_conversations, f, indent=2)

    print(f"\nSaved {len(full_conversations)} full conversations to intercom_full_sample.json")

    if full_conversations:
        print("\nFirst full conversation (preview):")
        print(json.dumps(full_conversations[0], indent=2)[:2000])

if __name__ == "__main__":
    main()