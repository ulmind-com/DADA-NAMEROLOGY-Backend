"""MongoDB data layer.

A thin typed repository over PyMongo. Documents are Pydantic models, so route code
keeps working with real objects (`user.email`, `report.type`) rather than raw dicts.

PyMongo is synchronous and thread-safe; FastAPI runs `def` endpoints in a threadpool,
so the driver's connection pool is used exactly as intended.
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterable, Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database as MongoDatabase
from pymongo.errors import OperationFailure

from app.core.config import settings

log = logging.getLogger("dada.mongo")

T = TypeVar("T")

ASC = ASCENDING
DESC = DESCENDING


# --------------------------------------------------------------------- client
_client: MongoClient | None = None


def close_client() -> None:
    """Close the pool and forget it, so the next `get_client()` reconnects."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            settings.MONGODB_URI,
            tz_aware=True,               # datetimes come back timezone-aware (UTC)
            tzinfo=UTC,
            serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS,
            appname="dada-numerology-api",
        )
    return _client


# ------------------------------------------------------------- serialisation
def encode(value: Any) -> Any:
    """Make a value safe for BSON: enums become strings, dates become ISO strings."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return value.isoformat()          # never range-queried, so a string is fine
    if isinstance(value, Mapping):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


class Repo(Generic[T]):
    """Typed access to one collection."""

    def __init__(self, collection: Collection, model: type[T]):
        self.col = collection
        self.model = model

    # ---- reads
    def _load(self, doc: Mapping | None) -> T | None:
        return self.model.model_validate(doc) if doc else None  # type: ignore[attr-defined]

    def get(self, doc_id: str | None) -> T | None:
        if not doc_id:
            return None
        return self._load(self.col.find_one({"_id": doc_id}))

    def find_one(self, flt: Mapping[str, Any]) -> T | None:
        return self._load(self.col.find_one(encode(dict(flt))))

    def find(
        self,
        flt: Mapping[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[T]:
        cur = self.col.find(encode(dict(flt or {})))
        if sort:
            cur = cur.sort(sort)
        if skip:
            cur = cur.skip(skip)
        if limit:
            cur = cur.limit(limit)
        return [self._load(d) for d in cur]  # type: ignore[misc]

    def count(self, flt: Mapping[str, Any] | None = None) -> int:
        return self.col.count_documents(encode(dict(flt or {})))

    def exists(self, flt: Mapping[str, Any]) -> bool:
        return self.col.count_documents(encode(dict(flt)), limit=1) > 0

    def distinct(self, field: str, flt: Mapping[str, Any] | None = None) -> list[Any]:
        return self.col.distinct(field, encode(dict(flt or {})))

    def aggregate(self, pipeline: Iterable[Mapping[str, Any]]) -> list[dict]:
        return list(self.col.aggregate([encode(dict(s)) for s in pipeline]))

    # ---- writes
    def insert(self, doc: T) -> T:
        self.col.insert_one(doc.to_mongo())  # type: ignore[attr-defined]
        return doc

    def update(self, doc_id: str, changes: Mapping[str, Any]) -> None:
        if changes:
            self.col.update_one({"_id": doc_id}, {"$set": encode(dict(changes))})

    def update_many(self, flt: Mapping[str, Any], changes: Mapping[str, Any]) -> int:
        return self.col.update_many(
            encode(dict(flt)), {"$set": encode(dict(changes))}
        ).modified_count

    def increment(self, doc_id: str, field: str, by: int = 1) -> None:
        self.col.update_one({"_id": doc_id}, {"$inc": {field: by}})

    def replace(self, doc: T) -> None:
        self.col.replace_one({"_id": doc.id}, doc.to_mongo(), upsert=True)  # type: ignore[attr-defined]

    def upsert(self, flt: Mapping[str, Any], changes: Mapping[str, Any]) -> None:
        self.col.update_one(encode(dict(flt)), {"$set": encode(dict(changes))}, upsert=True)

    def delete(self, doc_id: str) -> None:
        self.col.delete_one({"_id": doc_id})

    def delete_many(self, flt: Mapping[str, Any]) -> int:
        return self.col.delete_many(encode(dict(flt))).deleted_count


class DB:
    """All collections in one place — the object routes receive from `get_db`."""

    def __init__(self, database: MongoDatabase):
        from app.models import (
            AppSetting,
            AuditLog,
            OtpCode,
            RefreshToken,
            Report,
            Rule,
            User,
        )

        self.raw = database
        self.users: Repo[User] = Repo(database["users"], User)
        self.otps: Repo[OtpCode] = Repo(database["otp_codes"], OtpCode)
        self.refresh_tokens: Repo[RefreshToken] = Repo(database["refresh_tokens"], RefreshToken)
        self.reports: Repo[Report] = Repo(database["reports"], Report)
        self.rules: Repo[Rule] = Repo(database["rules"], Rule)
        self.settings: Repo[AppSetting] = Repo(database["app_settings"], AppSetting)
        self.audit: Repo[AuditLog] = Repo(database["audit_logs"], AuditLog)

    def delete_user_cascade(self, user_id: str) -> None:
        """Mongo has no foreign keys, so related documents are removed explicitly."""
        self.reports.delete_many({"user_id": user_id})
        self.refresh_tokens.delete_many({"user_id": user_id})
        self.users.delete(user_id)


def get_database() -> MongoDatabase:
    return get_client()[settings.MONGODB_DB]


def get_db() -> Generator[DB, None, None]:
    yield DB(get_database())


def _index(col: Collection, keys, **opts) -> None:
    """create_index, but rebuild the index when its options have changed."""
    try:
        col.create_index(keys, **opts)
    except OperationFailure as exc:
        if exc.code not in (85, 86):   # IndexOptionsConflict / IndexKeySpecsConflict
            raise
        wanted = {keys} if isinstance(keys, str) else {k for k, _ in keys}
        for existing in col.list_indexes():
            if existing["name"] != "_id_" and set(existing["key"]) == wanted:
                col.drop_index(existing["name"])
                log.info("Rebuilt index on %s.%s", col.name, ", ".join(sorted(wanted)))
                break
        col.create_index(keys, **opts)


def ensure_indexes(db: DB) -> None:
    """Idempotent — safe to run on every boot."""
    _index(db.users.col, "email", unique=True)
    # A sparse unique index would still collide on documents that store an explicit
    # null, so the uniqueness is scoped to documents where google_id is a string.
    _index(
        db.users.col,
        "google_id",
        unique=True,
        partialFilterExpression={"google_id": {"$type": "string"}},
    )
    _index(db.users.col, [("created_at", DESC)])
    _index(db.users.col, "role")

    _index(db.otps.col, [("email", ASC), ("purpose", ASC), ("created_at", DESC)])
    # Mongo removes expired OTPs on its own, one hour after they lapse.
    _index(db.otps.col, "expires_at", expireAfterSeconds=3600)

    _index(db.refresh_tokens.col, "token_hash")
    _index(db.refresh_tokens.col, "user_id")
    _index(db.refresh_tokens.col, "expires_at", expireAfterSeconds=0)

    _index(db.reports.col, [("user_id", ASC), ("created_at", DESC)])
    _index(db.reports.col, [("created_at", DESC)])
    _index(db.reports.col, "type")

    _index(db.rules.col, [("kind", ASC), ("key", ASC)], unique=True)
    _index(db.audit.col, [("created_at", DESC)])
    log.info("Mongo indexes ensured on %s", settings.MONGODB_DB)
