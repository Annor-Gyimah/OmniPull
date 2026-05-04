import sqlite3
import json
import os
import shutil
from modules.utils import log


def _get_schema():
    """
    Derive column list and JSON columns dynamically from DownloadItem
    so db_manager never drifts out of sync with the data model.
    """
    # Late import to avoid circular imports at module load time
    from modules.downloaditem import DownloadItem
    sample = DownloadItem()
    props = sample.get_persistent_properties()

    columns = list(props.keys())

    # Detect which values are complex types needing JSON serialization
    json_cols = set()
    for key, val in props.items():
        if isinstance(val, (list, dict)):
            json_cols.add(key)

    # 'scheduled' is a tuple/None at runtime but stored as JSON
    json_cols.add("scheduled")

    return columns, json_cols


# Build schema once at import time
_COLUMNS, _JSON_COLUMNS = _get_schema()

# ── Type coercion map ─────────────────────────────────────────────────────────
# Columns that must come back as specific Python types after SQLite TEXT storage.
# New numeric fields here if get_persistent_properties() grows.
_INT_COLUMNS = {
    "id", "size", "_downloaded", "audio_size", "remaining_parts",
    "_segment_size", "last_known_size", "last_known_progress",
    "queue_position", "schedule_retries", "retry_count", "status_code",
}
_FLOAT_COLUMNS: set = set()
_BOOL_COLUMNS = {"resumable", "in_queue"}


def _create_table_sql() -> str:
    cols = []
    for col in _COLUMNS:
        if col == "id":
            cols.append('"id" INTEGER PRIMARY KEY')
        else:
            cols.append(f'"{col}" TEXT')
    return f"CREATE TABLE IF NOT EXISTS downloads ({', '.join(cols)});"


def _upsert_sql() -> str:
    placeholders = ", ".join("?" for _ in _COLUMNS)
    col_list = ", ".join(f'"{c}"' for c in _COLUMNS)
    updates = ", ".join(f'"{c}"=excluded."{c}"' for c in _COLUMNS if c != "id")
    return (
        f'INSERT INTO downloads ({col_list}) VALUES ({placeholders}) '
        f'ON CONFLICT("id") DO UPDATE SET {updates};'
    )


class DatabaseManager:
    """Lightweight SQLite backend for OmniPull download persistence."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._create_sql = _create_table_sql()
        self._upsert_sql = _upsert_sql()
        self._init_db()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(self._create_sql)
            # New columns that exist in the model but not yet in the DB
            # (handles the case where DownloadItem grows new fields)
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(downloads)").fetchall()
            }
            for col in _COLUMNS:
                if col not in existing and col != "id":
                    conn.execute(f'ALTER TABLE downloads ADD COLUMN "{col}" TEXT')
            conn.commit()

    @staticmethod
    def _serialize(props: dict) -> tuple:
        """Convert get_persistent_properties() dict → ordered tuple for binding."""
        values = []
        for col in _COLUMNS:
            v = props.get(col)
            if col in _JSON_COLUMNS:
                v = json.dumps(v) if v is not None else None
            elif isinstance(v, (list, dict, tuple)):
                v = json.dumps(v)
            elif isinstance(v, bool):
                # bool before int check — bool is a subclass of int
                v = int(v)
            # Everything else goes in as-is; sqlite3 handles int/float/None/str
            values.append(v)
        return tuple(values)

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> dict:
        """Convert a DB row back to a dict with proper Python types."""
        d = dict(row)

        for col in _JSON_COLUMNS:
            if col in d and d[col] is not None:
                try:
                    d[col] = json.loads(d[col])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Coerce TEXT → int
        for col in _INT_COLUMNS:
            if col in d and d[col] is not None:
                try:
                    d[col] = int(float(str(d[col])))
                except (ValueError, TypeError):
                    d[col] = 0

        # Coerce TEXT → float
        for col in _FLOAT_COLUMNS:
            if col in d and d[col] is not None:
                try:
                    d[col] = float(d[col])
                except (ValueError, TypeError):
                    d[col] = 0.0

        # Coerce TEXT → bool  ("1"/"0", "True"/"False", 1/0)
        for col in _BOOL_COLUMNS:
            if col in d and d[col] is not None:
                raw = str(d[col]).strip().lower()
                d[col] = raw in ("1", "true", "yes")

        return d

    # ── Public API ────────────────────────────────────────────────────────────

    def upsert_download(self, props: dict):
        """Insert or update a single download record."""
        try:
            with self._connect() as conn:
                conn.execute(self._upsert_sql, self._serialize(props))
                conn.commit()
        except Exception as e:
            log(f"[DB] upsert_download failed: {e}", log_level=3)

    def upsert_many(self, props_list: list):
        """Batch insert/update — one transaction for the whole list."""
        try:
            rows = [self._serialize(p) for p in props_list]
            with self._connect() as conn:
                conn.executemany(self._upsert_sql, rows)
                conn.commit()
        except Exception as e:
            log(f"[DB] upsert_many failed: {e}", log_level=3)

    def delete_download(self, download_id: int):
        """Remove a download record by its id."""
        try:
            with self._connect() as conn:
                conn.execute('DELETE FROM downloads WHERE "id"=?', (download_id,))
                conn.commit()
        except Exception as e:
            log(f"[DB] delete_download failed: {e}", log_level=3)

    def load_all_downloads(self) -> list[dict]:
        """Return all rows as a list of properly-typed dicts."""
        try:
            col_list = ", ".join(f'"{c}"' for c in _COLUMNS)
            with self._connect() as conn:
                rows = conn.execute(
                    f"SELECT {col_list} FROM downloads"
                ).fetchall()
            return [self._deserialize(r) for r in rows]
        except Exception as e:
            log(f"[DB] load_all_downloads failed: {e}", log_level=3)
            return []
        
    def save_single_download(self, d):
        """Upsert one download item — use after status changes to avoid a full list write."""
        try:
            self.upsert_download(d.get_persistent_properties())
        except Exception as e:
            log(f"[DB] Error saving single download: {e}", log_level=3)


# ── One-time Migration ────────────────────────────────────────────────────────

def migrate_json_to_sqlite(cfg_path: str, db_path: str) -> bool:
    """
    Reads downloads.cfg (JSON) → SQLite, then renames the cfg to .bak.
    Returns True if migration ran, False if skipped (already done or no cfg).
    """
    if not os.path.exists(cfg_path):
        return False

    backup_path = cfg_path + ".bak"
    if os.path.exists(backup_path):
        return False

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = []

        db = DatabaseManager(db_path)
        db.upsert_many(data)

        shutil.move(cfg_path, backup_path)
        log(f"[DB] Migration complete: {len(data)} records → {db_path}", log_level=1)
        log(f"[DB] Original cfg backed up to: {backup_path}", log_level=1)
        return True

    except Exception as e:
        log(f"[DB] Migration failed: {e}", log_level=3)
        return False