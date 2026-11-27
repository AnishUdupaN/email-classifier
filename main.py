import datetime
import email
import json
import re
import sqlite3
from typing import Dict, List, Optional
from classifier import classify_email_with_ollama
from imap_client import *
import goa

import send_fcm_notifications

def dprint(string):
    with open("/home/anishudupan/email/new/file","a") as f:
        f.write(string)
        f.close()
dprint("started\n")
    
send_fcm_notifications.initialize_firebase()
def notify_user(sender_name, sender_email, subject, reasoning):
    send_fcm_notifications.send_to_topic("laptop-alerts",subject,"From: "+sender_name+' ('+sender_email+')\nReasoning: '+reasoning,priority="high")


# ==========================================
# 1. Database Setup & Helpers
# ==========================================

def init_db(db_path: str = "emails.db"):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                imap_uid INTEGER NOT NULL,
                account_email TEXT NOT NULL,
                sender_name TEXT,
                sender_email TEXT,
                subject TEXT,
                date_str TEXT,
                time_str TEXT,
                timestamp INTEGER,
                body_text TEXT,
                attachments_json TEXT,
                category TEXT DEFAULT 'unclassified',
                reasoning TEXT DEFAULT '',
                is_classified INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_account_uid ON emails(account_email, imap_uid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classified ON emails(is_classified)")
        conn.commit()


def get_latest_stored_uid(account_email: str, db_path: str = "emails.db") -> Optional[int]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(imap_uid) FROM emails WHERE account_email = ?",
            (account_email,),
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else None


def insert_unclassified_emails(email_records: List[Dict], db_path: str = "emails.db"):
    if not email_records:
        return

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for item in email_records:
            cursor.execute(
                """
                INSERT OR IGNORE INTO emails (
                    id, imap_uid, account_email, sender_name, sender_email,
                    subject, date_str, time_str, timestamp, body_text,
                    attachments_json, category, reasoning, is_classified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    item["id"],
                    item["imap_uid"],
                    item["account_email"],
                    item["sender_name"],
                    item["sender_email"],
                    item["subject"],
                    item["date_str"],
                    item["time_str"],
                    item["timestamp"],
                    item["body_text"],
                    json.dumps(item["attachments"]),
                    "unclassified",
                    "",
                ),
            )
        conn.commit()


def get_unclassified_emails(account_email: str, db_path: str = "emails.db") -> List[Dict]:
    """Fetches all emails that are currently pending classification."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, sender_name, sender_email, subject, body_text
            FROM emails
            WHERE account_email = ? AND is_classified = 0
            """,
            (account_email,),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_email_classification(
    email_id: str, category: str, reasoning: str, db_path: str = "emails.db"
):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE emails
            SET category = ?, reasoning = ?, is_classified = 1
            WHERE id = ?
            """,
            (category, reasoning, email_id),
        )
        conn.commit()


# ==========================================
# 2. IMAP Sync Routine (UID-Aware)
# ==========================================

def fetch_and_sync_emails(
    account_email: str,
    access_token: str,
    db_path: str = "/home/anishudupan/email/new/emails.db",
):
    init_db(db_path)
    last_uid = get_latest_stored_uid(account_email, db_path)

    mail = connect_imap(account_email, access_token)
    try:
        # Ensure the INBOX folder is actively selected
        mail.select("INBOX")

        if last_uid is not None:
            search_query = f"UID {last_uid + 1}:*"
        else:
            today_str = datetime.date.today().strftime("%d-%b-%Y")
            search_query = f"ON {today_str}"

        status, data = mail.uid("search", None, search_query)
        new_records = []

        if status == "OK" and data and data[0]:
            raw_uids = data[0].split()
            for uid_bytes in reversed(raw_uids):
                msg_uid = int(uid_bytes.decode("utf-8"))

                if last_uid is not None and msg_uid <= last_uid:
                    continue

                status, full_data = mail.uid(
                    "fetch", uid_bytes, "(BODYSTRUCTURE BODY.PEEK[HEADER] BODY.PEEK[1])"
                )
                if status != "OK" or not full_data:
                    continue

                header_bytes = b""
                part1_bytes = b""
                struct_str = ""

                for item in full_data:
                    if isinstance(item, tuple):
                        if b"HEADER" in item[0]:
                            header_bytes = item[1]
                        elif b"BODY[1]" in item[0] or b"BODY.PEEK[1]" in item[0]:
                            part1_bytes = item[1]
                        elif b"BODYSTRUCTURE" in item[0]:
                            struct_str = item[0].decode(errors="ignore")

                if not part1_bytes:
                    status_txt, text_data = mail.uid("fetch", uid_bytes, "(BODY.PEEK[TEXT])")
                    if status_txt == "OK" and text_data:
                        for item in text_data:
                            if isinstance(item, tuple) and b"TEXT" in item[0]:
                                part1_bytes = item[1]

                msg_hdr = email.message_from_bytes(header_bytes)
                s_name, s_email = parse_sender(msg_hdr.get("From", ""))
                dt_obj, d_str, t_str = parse_email_datetime(msg_hdr.get("Date", ""))
                subj = decode_mime_words(msg_hdr.get("Subject", "(No Subject)"))

                combined_msg = email.message_from_bytes(header_bytes + b"\r\n\r\n" + part1_bytes)
                body, _ = extract_body_and_attachments(combined_msg)

                attachments = []
                att_matches = re.finditer(
                    r'\("(?:IMAGE|APPLICATION|AUDIO|VIDEO|DOCUMENT)"\s+"([^"]+)"\s+\((.*?)\).*?\s+(\d+)\)',
                    struct_str,
                    re.IGNORECASE,
                )
                for m in att_matches:
                    sub_type = m.group(1).lower()
                    params = m.group(2)
                    size_b = int(m.group(3))
                    fn_m = re.search(r'"(?:NAME|FILENAME)"\s+"([^"]+)"', params, re.IGNORECASE)
                    fn = decode_mime_words(fn_m.group(1)) if fn_m else "attachment.bin"
                    attachments.append({
                        "filename": fn,
                        "type": f"file/{sub_type}",
                        "size_kb": round(size_b / 1024.0, 1),
                    })

                ts = int(dt_obj.timestamp()) if dt_obj else 0
                unique_id = f"{account_email}_{d_str}_{msg_uid}"

                new_records.append({
                    "id": unique_id,
                    "imap_uid": msg_uid,
                    "account_email": account_email,
                    "sender_name": s_name,
                    "sender_email": s_email,
                    "subject": subj,
                    "date_str": d_str,
                    "time_str": t_str,
                    "timestamp": ts,
                    "body_text": body,
                    "attachments": attachments,
                })

            # Store records safely in SQLite
            insert_unclassified_emails(new_records, db_path)

    finally:
        try:
            mail.close()
        except Exception:
            pass
        mail.logout()

    # Process all unclassified records in DB (handles new items and previously interrupted items)
    pending_emails = get_unclassified_emails(account_email, db_path)
    print(f"Found {len(pending_emails)} unclassified emails to process.")

    for rec in pending_emails:
        dprint(f"classifying {rec['sender_name']} {rec['sender_email']}\t")
        category, reasoning = classify_email_with_ollama(
            rec["sender_name"],
            rec["sender_email"],
            rec["subject"],
            rec["body_text"]
        )
        dprint(category+"\n")
        update_email_classification(rec["id"], category, reasoning, db_path)
        if category=="important" or category=="placement":
            notify_user(rec["sender_name"],rec["sender_email"],rec["subject"],reasoning)


if __name__ == "__main__":
    account_email, access_token = goa.get_default_account_token()
    fetch_and_sync_emails(account_email, access_token, "/home/anishudupan/email/new/emails.db")
