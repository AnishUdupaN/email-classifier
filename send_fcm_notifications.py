"""
Firebase Cloud Messaging (FCM) Push Notification Script

This script sends FCM push notifications with high priority (heads-up / floating banners)
and custom message payloads to Android devices or topics.

Prerequisites:
1. Install the Firebase Admin SDK for Python:
   pip install firebase-admin

2. Service Account Key:
   Ensure 'serviceAccountKey.json' is present in the root directory or python directory alongside this script.
   If needed, generate one from the Firebase Console:
   Project Settings > Service Accounts > Generate new private key.

Manual Execution Instructions:
1. Basic execution with default topic ("laptop-alerts"):
   python send_push.py

2. Send high priority heads-up push notification:
   python send_push.py --priority high

3. Send custom notification with title and body to a device token:
   python send_push.py --token "<FCM_DEVICE_TOKEN>" --title "Alert" --body "Important heads-up banner notification!" --priority high

4. Send to a topic with custom channel ID:
   python send_push.py --topic "laptop-alerts" --title "Laptop Alert" --body "Check this out!" --channel-id "my_channel"

5. Bulk push notifications from local JSON file:
   python send_push.py --json-file sample_notifications.json

6. Interactive Mode:
   python send_push.py --interactive
"""

import argparse
import json
import os
import sys
import time
import firebase_admin
from firebase_admin import credentials, messaging

# --- CONFIGURATION & DEFAULTS ---
DEFAULT_PRIORITY = "high"  # Options: 'high' or 'normal'
DEFAULT_CHANNEL_ID = "my_channel"
DEFAULT_TOPIC = "laptop-alerts"

# Default target token or topic (token takes precedence if set)
TARGET_TOKEN = ""
TARGET_TOPIC = DEFAULT_TOPIC

DEFAULT_TITLE = "Test Notification"
DEFAULT_BODY = "This is a test message from the Python send_push.py script!"

SERVICE_ACCOUNT_FILE = 'serviceAccountKey.json'


def get_service_account_path():
    """Locate the service account key file relative to current directory, script directory, or python folder."""
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return SERVICE_ACCOUNT_FILE

    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_relative_path = os.path.join(script_dir, SERVICE_ACCOUNT_FILE)
    if os.path.exists(script_relative_path):
        return script_relative_path

    python_sub_path = os.path.join(script_dir, 'python', SERVICE_ACCOUNT_FILE)
    if os.path.exists(python_sub_path):
        return python_sub_path

    parent_path = os.path.join(os.path.dirname(script_dir), SERVICE_ACCOUNT_FILE)
    if os.path.exists(parent_path):
        return parent_path

    return SERVICE_ACCOUNT_FILE


def initialize_firebase():
    """Initialize the Firebase Admin SDK using the service account key."""
    sa_path = get_service_account_path()
    if not os.path.exists(sa_path):
        print(f"Error: Could not find '{SERVICE_ACCOUNT_FILE}'.")
        print("Please download it from the Firebase Console (Project Settings > Service Accounts) and place it in the project directory.")
        sys.exit(1)

    try:
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        sys.exit(1)


def send_to_token(token, title, body, priority=DEFAULT_PRIORITY, channel_id=DEFAULT_CHANNEL_ID):
    """
    Send push notification to a specific FCM registration token with specified Android priority and channel.
    Configures both AndroidConfig and AndroidNotification for high-priority heads-up floating banners.
    """
    priority_val = priority.lower() if priority else DEFAULT_PRIORITY
    if priority_val not in ['high', 'normal']:
        print(f"Warning: Invalid priority '{priority}'. Falling back to '{DEFAULT_PRIORITY}'.")
        priority_val = DEFAULT_PRIORITY

    android_notification = messaging.AndroidNotification(
        channel_id=channel_id,
        default_sound=True,
        default_vibrate_timings=True,
    )

    android_config = messaging.AndroidConfig(
        priority=priority_val,
        notification=android_notification,
    )

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        android=android_config,
        token=token,
    )

    try:
        response = messaging.send(message)
        print(f"Successfully sent message to token with priority '{priority_val}' (channel: '{channel_id}'). Message ID: {response}")
        return response
    except Exception as e:
        print(f"Error sending message to token: {e}")
        return None


def send_to_topic(topic, title, body, priority=DEFAULT_PRIORITY, channel_id=DEFAULT_CHANNEL_ID):
    """
    Send push notification to an FCM topic with specified Android priority and channel.
    Configures both AndroidConfig and AndroidNotification for high-priority heads-up floating banners.
    """
    if not topic:
        print("Error: Topic is empty.")
        return None

    # Sanitize topic string: FCM Admin SDK expects topic name without '/topics/' prefix
    clean_topic = topic.replace('/topics/', '') if topic.startswith('/topics/') else topic

    priority_val = priority.lower() if priority else DEFAULT_PRIORITY
    if priority_val not in ['high', 'normal']:
        print(f"Warning: Invalid priority '{priority}'. Falling back to '{DEFAULT_PRIORITY}'.")
        priority_val = DEFAULT_PRIORITY

    android_notification = messaging.AndroidNotification(
        channel_id=channel_id,
        default_sound=True,
        default_vibrate_timings=True,
    )

    android_config = messaging.AndroidConfig(
        priority=priority_val,
        notification=android_notification,
    )

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        android=android_config,
        topic=clean_topic,
    )

    try:
        response = messaging.send(message)
        print(f"Successfully sent message to topic '{clean_topic}' with priority '{priority_val}' (channel: '{channel_id}'). Message ID: {response}")
        return response
    except Exception as e:
        print(f"Error sending message to topic: {e}")
        return None


def send_bulk_from_json(json_file_path, token=None, topic=None, channel_id=DEFAULT_CHANNEL_ID):
    """
    Parse notification contents from a local JSON file and bulk push those notifications to the target.

    The JSON file can contain either a list of notification objects or a dict with a 'notifications' list.
    Each individual item can contain:
      - 'title': Notification title
      - 'body': Notification body
      - 'priority': Notification priority ('high' or 'normal')
      - 'channel_id': (Optional) Channel ID override for this item
      - 'token': (Optional) FCM target token override for this item
      - 'topic': (Optional) FCM target topic override for this item
    """
    resolved_path = json_file_path
    if not os.path.exists(resolved_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.join(script_dir, json_file_path)
        if os.path.exists(alt_path):
            resolved_path = alt_path
        else:
            print(f"Error: Could not find JSON file '{json_file_path}'.")
            return []

    try:
        with open(resolved_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error parsing JSON file '{resolved_path}': {e}")
        return []

    if isinstance(data, dict) and "notifications" in data:
        items = data["notifications"]
    elif isinstance(data, list):
        items = data
    else:
        print(f"Error: JSON content in '{resolved_path}' must be a list of objects or a dict containing a 'notifications' list.")
        return []

    if not isinstance(items, list):
        print(f"Error: 'notifications' entry in '{resolved_path}' is not a list.")
        return []

    print(f"\n--- Starting Bulk Push ({len(items)} notification(s) from '{json_file_path}') ---")

    responses = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            print(f"[{idx}/{len(items)}] Skipping invalid item (not a dict): {item}")
            continue

        item_title = item.get("title", DEFAULT_TITLE)
        item_body = item.get("body", DEFAULT_BODY)
        item_priority = item.get("priority", DEFAULT_PRIORITY)
        item_channel = item.get("channel_id", channel_id)

        target_tok = item.get("token", token)
        target_top = item.get("topic", topic)

        print(f"\n[{idx}/{len(items)}] Title: '{item_title}', Body: '{item_body}', Priority: '{item_priority}'")

        if target_tok:
            print(f"  Target Token: {target_tok[:20]}...")
            resp = send_to_token(target_tok, item_title, item_body, priority=item_priority, channel_id=item_channel)
        elif target_top:
            print(f"  Target Topic: {target_top}")
            resp = send_to_topic(target_top, item_title, item_body, priority=item_priority, channel_id=item_channel)
        else:
            print(f"  Error: No target token or topic specified for notification {idx}.")
            resp = None

        responses.append(resp)
        if idx < len(items):
            time.sleep(0.5)

    successful = sum(1 for r in responses if r is not None)
    print(f"\n--- Bulk Push Completed: {successful}/{len(items)} notifications sent successfully. ---\n")
    return responses


def prompt_interactive_inputs():
    """Prompt user interactively for priority and message options if requested."""
    print("\n--- Interactive FCM Priority & Message Configuration ---")

    json_file_input = input("Enter path to local JSON file for bulk push (press Enter to skip): ").strip()

    if json_file_input:
        target_token_input = input("Enter target token (press Enter to skip): ").strip()
        if target_token_input:
            return None, None, None, DEFAULT_CHANNEL_ID, target_token_input, None, json_file_input

        target_topic_input = input(f"Enter target topic [{DEFAULT_TOPIC}]: ").strip()
        if not target_topic_input:
            target_topic_input = DEFAULT_TOPIC
        return None, None, None, DEFAULT_CHANNEL_ID, None, target_topic_input, json_file_input

    priority_input = input(f"Enter notification priority (high/normal) [{DEFAULT_PRIORITY}]: ").strip().lower()
    if priority_input not in ['high', 'normal']:
        priority_input = DEFAULT_PRIORITY

    title_input = input(f"Enter notification title [{DEFAULT_TITLE}]: ").strip()
    if not title_input:
        title_input = DEFAULT_TITLE

    body_input = input(f"Enter notification body [{DEFAULT_BODY}]: ").strip()
    if not body_input:
        body_input = DEFAULT_BODY

    channel_input = input(f"Enter notification channel ID [{DEFAULT_CHANNEL_ID}]: ").strip()
    if not channel_input:
        channel_input = DEFAULT_CHANNEL_ID

    target_token_input = input("Enter target token (press Enter to skip): ").strip()
    if target_token_input:
        return priority_input, title_input, body_input, channel_input, target_token_input, None, None

    target_topic_input = input(f"Enter target topic [{DEFAULT_TOPIC}]: ").strip()
    if target_topic_input:
        return priority_input, title_input, body_input, channel_input, None, target_topic_input, None

    token = TARGET_TOKEN if TARGET_TOKEN else None
    topic = TARGET_TOPIC if TARGET_TOPIC else DEFAULT_TOPIC
    return priority_input, title_input, body_input, channel_input, token, topic, None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Send FCM push notifications with high priority heads-up support ('high' or 'normal').",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python send_push.py --priority high
  python send_push.py --token "<TOKEN>" --title "Alert" --body "Important notification" --priority high
  python send_push.py --topic "laptop-alerts" --priority high --channel-id "my_channel"
  python send_push.py --json-file sample_notifications.json
  python send_push.py --interactive
        """
    )
    parser.add_argument(
        "-p", "--priority",
        choices=["high", "normal"],
        default=None,
        help=f"Notification priority level ('high' or 'normal'). Fallback default: '{DEFAULT_PRIORITY}'"
    )
    parser.add_argument(
        "-c", "--channel-id",
        type=str,
        default=DEFAULT_CHANNEL_ID,
        help=f"Android Notification Channel ID. Default: '{DEFAULT_CHANNEL_ID}'"
    )
    parser.add_argument(
        "-t", "--token",
        type=str,
        default=None,
        help="Target FCM device registration token"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Target FCM topic name"
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help=f"Notification title. Default: '{DEFAULT_TITLE}'"
    )
    parser.add_argument(
        "-b", "--body",
        type=str,
        default=None,
        help=f"Notification body. Default: '{DEFAULT_BODY}'"
    )
    parser.add_argument(
        "-j", "--json-file",
        type=str,
        default=None,
        help="Path to local JSON file containing notification contents for bulk push"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run interactive prompt to set priority and message details"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.interactive:
        priority, title, body, channel_id, token, topic, json_file = prompt_interactive_inputs()
    else:
        json_file = args.json_file
        priority = args.priority if args.priority else DEFAULT_PRIORITY
        title = args.title if args.title else DEFAULT_TITLE
        body = args.body if args.body else DEFAULT_BODY
        channel_id = args.channel_id if args.channel_id else DEFAULT_CHANNEL_ID

        if args.token:
            token = args.token
            topic = None
        elif args.topic:
            token = None
            topic = args.topic
        elif TARGET_TOKEN:
            token = TARGET_TOKEN
            topic = None
        elif TARGET_TOPIC:
            token = None
            topic = TARGET_TOPIC
        else:
            token = None
            topic = DEFAULT_TOPIC

    initialize_firebase()

    if json_file:
        send_bulk_from_json(json_file, token=token, topic=topic, channel_id=channel_id)
        return

    print(f"Notification Configuration:")
    print(f"  Priority   : {priority}")
    print(f"  Channel ID : {channel_id}")
    print(f"  Title      : {title}")
    print(f"  Body       : {body}")

    if token:
        print(f"Sending to token: {token[:20]}...")
        send_to_token(token, title, body, priority=priority, channel_id=channel_id)
    elif topic:
        print(f"Sending to topic: {topic}...")
        send_to_topic(topic, title, body, priority=priority, channel_id=channel_id)
    else:
        print("Error: Please specify either a target token (--token) or a target topic (--topic), or configure TARGET_TOKEN / TARGET_TOPIC in the script.")


if __name__ == "__main__":
    main()
