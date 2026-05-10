import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

try:
    from .config import CACHE_FILE
except ImportError:
    from config import CACHE_FILE


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in value.items()}
    return str(value)


def load_cache() -> Dict[str, Any]:
    if not CACHE_FILE.exists():
        return {"entries": {}}

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            return {"entries": {}}
        data.setdefault("entries", {})
        return data
    except (json.JSONDecodeError, OSError):
        return {"entries": {}}


def save_cache(data: Dict[str, Any]) -> None:
    with CACHE_FILE.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def make_cache_key(
    uri: str,
    username: str,
    database: str,
    query: str,
    row_limit: int,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    params_text = json.dumps(params or {}, sort_keys=True)
    key_text = f"{uri}|{username}|{database}|{row_limit}|{query.strip()}|{params_text}"
    return hashlib.sha256(key_text.encode("utf-8")).hexdigest()


def query_looks_write_operation(query: str) -> bool:
    upper = query.upper()
    blocked = [" CREATE ", " MERGE ", " DELETE ", " SET ", " REMOVE ", " DROP ", " LOAD CSV "]
    padded = f" {upper} "
    return any(keyword in padded for keyword in blocked)


def run_online_query(
    uri: str,
    username: str,
    password: str,
    database: str,
    query: str,
    row_limit: int,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()

        effective_query = query.strip().rstrip(";")
        query_params = dict(params or {})
        if "LIMIT" not in effective_query.upper() and "$row_limit" not in effective_query:
            effective_query = f"{effective_query}\nLIMIT $row_limit"
            query_params["row_limit"] = row_limit

        with driver.session(database=database) as session:
            result = session.run(effective_query, **query_params)
            rows = [
                {k: normalize_value(v) for k, v in record.data().items()}
                for record in result
            ]
        return rows, "online"
    finally:
        driver.close()


def get_data_with_fallback(
    uri: str,
    username: str,
    password: str,
    database: str,
    query: str,
    row_limit: int,
    params: Optional[Dict[str, Any]] = None,
    prefer_cache: bool = False,
) -> Tuple[List[Dict[str, Any]], str, str]:
    cache = load_cache()
    cache_key = make_cache_key(uri, username, database, query, row_limit, params)
    entries = cache.get("entries", {})
    cached = entries.get(cache_key)

    if prefer_cache and cached and "rows" in cached:
        msg = f"Loaded from cache (saved at {cached.get('fetched_at', 'unknown time')})."
        return cached["rows"], "cache", msg

    try:
        rows, source = run_online_query(uri, username, password, database, query, row_limit, params=params)
        entries[cache_key] = {
            "uri": uri,
            "username": username,
            "database": database,
            "query": query.strip(),
            "params": params or {},
            "row_limit": row_limit,
            "fetched_at": utc_now_iso(),
            "rows": rows,
        }
        cache["entries"] = entries
        save_cache(cache)
        return rows, source, "Connected to database. Fresh data loaded and cache updated."
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        if cached and "rows" in cached:
            msg = (
                "Database is offline/unreachable. Showing cached data from "
                f"{cached.get('fetched_at', 'unknown time')}. Error: {exc}"
            )
            return cached["rows"], "cache", msg
        raise RuntimeError(
            "Database is offline/unreachable and no cached result exists for this query. "
            f"Original error: {exc}"
        ) from exc


def cached_entries_for_ui() -> List[Dict[str, Any]]:
    entries = load_cache().get("entries", {})
    result = []
    for _, entry in entries.items():
        params = entry.get("params", {})
        if isinstance(params, dict):
            params_text = json.dumps(params, sort_keys=True)
        else:
            params_text = "{}"
        result.append(
            {
                "fetched_at": entry.get("fetched_at", ""),
                "database": entry.get("database", ""),
                "row_limit": entry.get("row_limit", ""),
                "query": entry.get("query", ""),
                "params": params_text,
                "rows": len(entry.get("rows", [])),
            }
        )
    result.sort(key=lambda x: x.get("fetched_at", ""), reverse=True)
    return result
