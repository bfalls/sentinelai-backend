"""Admin CLI for managing SentinelAI API keys.

Usage examples:
    python scripts/admin_api_keys.py create --email user@example.com --label "TAK plugin"
    python scripts/admin_api_keys.py list
    python scripts/admin_api_keys.py revoke --prefix abcd1234 --yes
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
import sys

from app.config import settings
from app.db import SessionLocal, init_db
from app.db_models import ApiKey
from app.security.api_keys import generate_api_key, hash_api_key, key_prefix


def _ensure_pepper() -> str:
    if not settings.api_key_pepper:
        sys.stderr.write("API key pepper must be configured to manage API keys.\n")
        raise SystemExit(1)
    return settings.api_key_pepper


def _get_session():
    init_db()
    return SessionLocal()


def _parse_expiration(args) -> datetime | None:
    if args.expires_at:
        return datetime.fromisoformat(args.expires_at)
    if args.expires_in:
        return datetime.utcnow() + timedelta(days=args.expires_in)
    return None


def cmd_create(args) -> None:
    pepper = _ensure_pepper()
    session = _get_session()
    try:
        expires_at = _parse_expiration(args)
        plaintext_key = generate_api_key(prefix="sk_test_sentinel" if args.test else "sk_sentinel")
        api_key = ApiKey(
            key_prefix=key_prefix(plaintext_key),
            key_hash=hash_api_key(plaintext_key, pepper),
            holder_email=args.email,
            holder_label=args.label,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            notes=args.notes,
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)

        output = {
            "id": api_key.id,
            "key_prefix": api_key.key_prefix,
            "holder_email": api_key.holder_email,
            "holder_label": api_key.holder_label,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "notes": api_key.notes,
            "api_key": plaintext_key,
        }
        if args.json:
            print(json.dumps(output, indent=2))
        else:
            print("API key created (store this secret securely, it will not be shown again):")
            print(f"  id: {api_key.id}")
            print(f"  prefix: {api_key.key_prefix}")
            print(f"  holder: {api_key.holder_email} ({api_key.holder_label or 'n/a'})")
            if api_key.expires_at:
                print(f"  expires_at: {api_key.expires_at.isoformat()}")
            print(f"  api_key: {plaintext_key}")
    finally:
        session.close()


def cmd_list(args) -> None:
    session = _get_session()
    try:
        query = session.query(ApiKey)
        if args.email:
            query = query.filter_by(holder_email=args.email)
        if not args.show_revoked:
            query = query.filter(ApiKey.revoked_at.is_(None))

        keys = query.order_by(ApiKey.created_at.desc()).all()
        output = [
            {
                "id": key.id,
                "key_prefix": key.key_prefix,
                "holder_email": key.holder_email,
                "holder_label": key.holder_label,
                "created_at": key.created_at.isoformat() if key.created_at else None,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
            }
            for key in keys
        ]

        if len(keys) == 0:
            print("No API keys found.")
        elif args.json:
            print(json.dumps(output, indent=2))
        else:
            for item in output:
                print(
                    f"{item['id']}: prefix={item['key_prefix']} email={item['holder_email']}"
                    f" label={item['holder_label'] or 'n/a'} expires={item['expires_at'] or 'none'}"
                    f" revoked={item['revoked_at'] or 'active'}"
                )
    finally:
        session.close()


def cmd_revoke(args) -> None:
    session = _get_session()
    try:
        target = None
        if args.id is not None:
            target = session.get(ApiKey, args.id)
        elif args.prefix:
            target = session.query(ApiKey).filter_by(key_prefix=args.prefix).first()

        if not target:
            sys.stderr.write("API key not found.\n")
            raise SystemExit(1)

        if target.revoked_at is not None:
            print("API key is already revoked.")
            return

        if not args.yes:
            confirmation = input(
                f"Revoke API key {target.key_prefix} for {target.holder_email}? [y/N]: "
            ).strip().lower()
            if confirmation not in {"y", "yes"}:
                print("Cancelled.")
                return

        target.revoked_at = datetime.utcnow()
        session.add(target)
        session.commit()
        print(f"API key {target.key_prefix} revoked at {target.revoked_at.isoformat()}")
    finally:
        session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SentinelAI API keys")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create", help="Create a new API key")
    create_cmd.add_argument("--email", required=True, help="Email address for the key holder")
    create_cmd.add_argument("--label", help="Label or device name")
    create_cmd.add_argument("--expires-in", type=int, help="Expiration in days")
    create_cmd.add_argument("--expires-at", help="Expiration timestamp in ISO format")
    create_cmd.add_argument("--notes", help="Optional notes for the key")
    create_cmd.add_argument("--test", action="store_true", help="Generate a test-only key")
    create_cmd.add_argument("--json", action="store_true", help="Return JSON output")
    create_cmd.set_defaults(func=cmd_create)

    list_cmd = sub.add_parser("list", help="List API keys")
    list_cmd.add_argument("--email", help="Filter by holder email")
    list_cmd.add_argument("--show-revoked", action="store_true", help="Include revoked keys")
    list_cmd.add_argument("--json", action="store_true", help="Return JSON output")
    list_cmd.set_defaults(func=cmd_list)

    revoke_cmd = sub.add_parser("revoke", help="Revoke an API key")
    revoke_cmd.add_argument("--id", type=int, help="ID of the API key to revoke")
    revoke_cmd.add_argument("--prefix", help="Key prefix of the API key to revoke")
    revoke_cmd.add_argument("--yes", action="store_true", help="Confirm revocation without prompt")
    revoke_cmd.set_defaults(func=cmd_revoke)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
