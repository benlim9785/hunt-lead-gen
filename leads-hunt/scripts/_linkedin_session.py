from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Callable

LINKEDIN_AUTH_COOKIE_NAMES = ("li_at", "JSESSIONID")
LINKEDIN_REQUIRED_COOKIE_NAMES = ("li_at",)
_CHROME_EPOCH_OFFSET_SECONDS = 11644473600


StatusFn = Callable[[str], None]


def _now_unix() -> int:
    return int(time.time())


def chrome_ts_to_unix(chrome_ts: int | None) -> int | None:
    if not chrome_ts:
        return None
    try:
        return int(chrome_ts / 1_000_000 - _CHROME_EPOCH_OFFSET_SECONDS)
    except Exception:
        return None


def cookie_db_path(profile_dir: str | Path) -> Path:
    profile_dir = Path(profile_dir)
    default_cookie_db = profile_dir / "Default" / "Cookies"
    if default_cookie_db.exists():
        return default_cookie_db
    return profile_dir / "Cookies"


def chromium_profile_candidates(primary_profile_dir: str | Path) -> list[Path]:
    primary = Path(primary_profile_dir).expanduser().resolve()
    candidates = [primary]

    env_candidates = [
        os.environ.get("LEADS_HUNT_LIVE_CHROMIUM_PROFILE"),
        os.environ.get("CHROMIUM_USER_DATA_DIR"),
        os.environ.get("CHROME_USER_DATA_DIR"),
    ]
    for raw in env_candidates:
        if raw:
            candidates.append(Path(raw).expanduser().resolve())

    candidates.extend([
        Path.home() / ".config" / "chromium",
        primary.parent,
    ])

    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except FileNotFoundError:
            candidate = candidate.expanduser()
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def _fetch_linkedin_auth_cookie_rows(cookie_db: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{cookie_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT host_key, name, value, length(value) AS value_len,
                   length(encrypted_value) AS encrypted_value_len,
                   expires_utc, is_httponly, is_secure, last_update_utc
            FROM cookies
            WHERE host_key LIKE ?
              AND name IN (?, ?)
            ORDER BY
              CASE name WHEN 'li_at' THEN 0 ELSE 1 END,
              host_key
            """,
            ("%linkedin.com%", *LINKEDIN_AUTH_COOKIE_NAMES),
        ).fetchall()
    finally:
        conn.close()


def inspect_profile_session(profile_dir: str | Path) -> dict:
    profile_dir = Path(profile_dir).expanduser().resolve()
    cookie_db = cookie_db_path(profile_dir)
    result = {
        "profile_dir": str(profile_dir),
        "cookie_db": str(cookie_db),
        "exists": cookie_db.exists(),
        "auth_cookies": [],
        "has_auth_cookie": False,
    }
    if not cookie_db.exists():
        return result

    try:
        rows = _fetch_linkedin_auth_cookie_rows(cookie_db)
    except sqlite3.Error as exc:
        result["error"] = f"sqlite:{exc}"
        return result

    now = _now_unix()
    cookies = []
    for row in rows:
        expires_unix = chrome_ts_to_unix(row["expires_utc"])
        is_session_cookie = not bool(row["expires_utc"])
        looks_present = bool(row["value_len"] or row["encrypted_value_len"])
        not_expired = is_session_cookie or expires_unix is None or expires_unix > now
        cookies.append({
            "host_key": row["host_key"],
            "name": row["name"],
            "has_value": looks_present,
            "expires_unix": expires_unix,
            "is_session_cookie": is_session_cookie,
            "is_secure": bool(row["is_secure"]),
            "is_httponly": bool(row["is_httponly"]),
            "last_update_unix": chrome_ts_to_unix(row["last_update_utc"]),
            "valid": looks_present and not_expired,
        })

    result["auth_cookies"] = cookies
    result["has_auth_cookie"] = any(
        cookie["valid"] and cookie["name"] in LINKEDIN_REQUIRED_COOKIE_NAMES
        for cookie in cookies
    )
    result["has_secondary_cookie_signal"] = any(cookie["valid"] for cookie in cookies)
    return result


def choose_best_session_source(primary_profile_dir: str | Path) -> dict | None:
    best: dict | None = None
    for candidate in chromium_profile_candidates(primary_profile_dir):
        info = inspect_profile_session(candidate)
        if not info.get("has_auth_cookie"):
            continue
        if best is None:
            best = info
            continue
        best_count = len(best.get("auth_cookies", []))
        info_count = len(info.get("auth_cookies", []))
        if info_count > best_count:
            best = info
            continue
        if info_count == best_count:
            best_mtime = Path(best["cookie_db"]).stat().st_mtime if Path(best["cookie_db"]).exists() else 0
            info_mtime = Path(info["cookie_db"]).stat().st_mtime if Path(info["cookie_db"]).exists() else 0
            if info_mtime > best_mtime:
                best = info
    return best


def sync_cookie_db(source_profile_dir: str | Path, target_profile_dir: str | Path, status: StatusFn | None = None) -> Path:
    source_profile_dir = Path(source_profile_dir).expanduser().resolve()
    target_profile_dir = Path(target_profile_dir).expanduser().resolve()
    source_db = cookie_db_path(source_profile_dir)
    target_db = cookie_db_path(target_profile_dir)
    target_db.parent.mkdir(parents=True, exist_ok=True)

    if status:
        status(f"Sync LinkedIn cookie DB: {source_db} -> {target_db}")

    src = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    dst = sqlite3.connect(target_db)
    try:
        src.backup(dst)
        src.row_factory = sqlite3.Row
        cookie_columns = [row[1] for row in src.execute("PRAGMA table_info(cookies)").fetchall()]
        select_sql = (
            f"SELECT {', '.join(cookie_columns)} FROM cookies "
            "WHERE host_key LIKE ?"
        )
        linkedin_rows = src.execute(select_sql, ("%linkedin.com%",)).fetchall()
        if linkedin_rows:
            dst.execute("DELETE FROM cookies WHERE host_key LIKE ?", ("%linkedin.com%",))
            insert_sql = (
                f"INSERT INTO cookies ({', '.join(cookie_columns)}) "
                f"VALUES ({', '.join('?' for _ in cookie_columns)})"
            )
            dst.executemany(
                insert_sql,
                [tuple(row[col] for col in cookie_columns) for row in linkedin_rows],
            )
            dst.commit()
    finally:
        dst.close()
        src.close()

    for suffix in ("-journal", "-wal", "-shm"):
        src_sidecar = Path(str(source_db) + suffix)
        dst_sidecar = Path(str(target_db) + suffix)
        if src_sidecar.exists():
            shutil.copy2(src_sidecar, dst_sidecar)
        else:
            dst_sidecar.unlink(missing_ok=True)

    return target_db


def ensure_session_profile(primary_profile_dir: str | Path, status: StatusFn | None = None) -> dict:
    primary_profile_dir = Path(primary_profile_dir).expanduser().resolve()
    primary = inspect_profile_session(primary_profile_dir)
    if primary.get("has_auth_cookie"):
        if status:
            status(
                "LinkedIn auth cookies already present in leads-hunt profile "
                f"({primary['cookie_db']})"
            )
        return {
            "ok": True,
            "active_profile_dir": str(primary_profile_dir),
            "source": "primary",
            "details": primary,
            "synced": False,
        }

    best = choose_best_session_source(primary_profile_dir)
    if best and Path(best["profile_dir"]) != primary_profile_dir:
        if status:
            status(
                "LinkedIn auth cookies not present in leads-hunt profile; found a live "
                f"authenticated Chromium profile at {best['profile_dir']}"
            )
        sync_cookie_db(best["profile_dir"], primary_profile_dir, status=status)
        refreshed = inspect_profile_session(primary_profile_dir)
        return {
            "ok": refreshed.get("has_auth_cookie", False),
            "active_profile_dir": str(primary_profile_dir),
            "source": best["profile_dir"],
            "details": refreshed,
            "synced": True,
        }

    if status:
        status(
            "No valid LinkedIn auth cookies found in any known Chromium profile. "
            "Need the AE to log in via the live VNC browser first."
        )
    return {
        "ok": False,
        "active_profile_dir": str(primary_profile_dir),
        "source": None,
        "details": primary,
        "synced": False,
    }
