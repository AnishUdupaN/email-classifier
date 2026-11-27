import json
import subprocess
import sys


def list_goa_google_accounts():
    """Returns a list of tuples: (account_path, presentation_identity/email)"""
    cmd = [
        "busctl",
        "--user",
        "--json=short",
        "call",
        "org.gnome.OnlineAccounts",
        "/org/gnome/OnlineAccounts",
        "org.freedesktop.DBus.ObjectManager",
        "GetManagedObjects",
    ]
    try:
        out = subprocess.check_output(cmd, text=True)
    except Exception as err:
        print(f"Error querying GOA via busctl: {err}")
        return []

    try:
        objects = json.loads(out)["data"][0]
        accounts = []
        for path, interfaces in objects.items():
            acct = interfaces.get("org.gnome.OnlineAccounts.Account", {})
            provider = acct.get("ProviderType", {}).get("data")
            if provider == "google":
                ident = acct.get("PresentationIdentity", {}).get("data")
                accounts.append((path, ident))
        return accounts
    except Exception as err:
        print(f"Error parsing GOA output: {err}")
        return []


def get_access_token(account_path):
    """Retrieves an OAuth2 access token for the given GOA account path."""
    cmd = [
        "busctl",
        "--user",
        "--json=short",
        "call",
        "org.gnome.OnlineAccounts",
        account_path,
        "org.gnome.OnlineAccounts.OAuth2Based",
        "GetAccessToken",
    ]
    try:
        out = subprocess.check_output(cmd, text=True)
        return json.loads(out)["data"][0]
    except Exception as err:
        print(f"Failed to fetch access token for {account_path}: {err}")
        raise RuntimeError(f"Could not get access token for path {account_path}: {err}")


def get_default_account_token():
    """Discovers the default Google GOA account and returns (email, access_token)."""
    accounts = list_goa_google_accounts()
    if not accounts:
        raise RuntimeError("No Google accounts discovered in GNOME Online Accounts.")

    # Default to first account or preferred rnsit account if available
    selected_path, selected_email = accounts[0]
    for path, email_addr in accounts:
        if "rnsit" in email_addr.lower():
            selected_path, selected_email = path, email_addr
            break

    token = get_access_token(selected_path)
    return selected_email, token
