"""Storage service — project CRUD via MongoDB.

Each project is a single self-contained document in the `projects` collection.
All state, timestamps, parsed scripts, pages, characters, and trailer data
live inside that one document — no cross-contamination, no shared state.

Supports MongoDB (primary) and JSON file fallback (offline dev).
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

from app.config.settings import settings
from app.models.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectStatus,
    ProjectUpdate,
    ParsedScript,
    CharacterSheet,
    PanelPage,
    TrailerProject,
)

logger = logging.getLogger(__name__)

# ── MongoDB client ──────────────────────────────────────────────────

_mongo_client: Optional[AsyncIOMotorClient] = None
_db = None
_use_json_fallback = False

# ── JSON fallback (offline dev) ─────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "projects"


def _ensure_data_dir():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_json(project_id: str, data: dict) -> None:
    _ensure_data_dir()
    with open(_DATA_DIR / f"{project_id}.json", "w") as f:
        json.dump(data, f, indent=2, default=str)


def _load_json(project_id: str) -> Optional[dict]:
    path = _DATA_DIR / f"{project_id}.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def _list_json(limit: int = 50) -> list[tuple[str, dict]]:
    _ensure_data_dir()
    items = []
    for path in _DATA_DIR.glob("*.json"):
        try:
            with open(path, "r") as f:
                items.append((path.stem, json.load(f)))
        except (json.JSONDecodeError, IOError):
            pass
    items.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    return items[:limit]


def _delete_json(project_id: str) -> bool:
    path = _DATA_DIR / f"{project_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# ── Init ────────────────────────────────────────────────────────────

def _init_storage():
    """Initialize MongoDB connection. Falls back to JSON files if unavailable."""
    global _mongo_client, _db, _use_json_fallback

    if _db is not None or _use_json_fallback:
        return  # Already initialized

    uri = settings.mongodb_uri
    db_name = settings.mongodb_database

    try:
        _mongo_client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=3000)
        _db = _mongo_client[db_name]
        logger.info(f"🍃 MongoDB client ready: {uri} / {db_name}")
    except Exception as e:
        _use_json_fallback = True
        _ensure_data_dir()
        count = len(list(_DATA_DIR.glob("*.json")))
        logger.warning(f"⚠️  MongoDB unavailable ({e}), using JSON fallback ({count} projects)")


def get_collection():
    """Get the projects collection."""
    if _db is None and not _use_json_fallback:
        _init_storage()
    if _use_json_fallback or _db is None:
        return None
    return _db["projects"]


# ── Helpers ─────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _doc_to_response(doc: dict) -> ProjectResponse:
    """Convert a MongoDB document to a ProjectResponse."""
    project_id = doc.get("project_id", doc.get("_id", ""))

    parsed = None
    if doc.get("parsed_script"):
        parsed = ParsedScript(**doc["parsed_script"])

    characters = [CharacterSheet(**c) for c in (doc.get("characters") or [])]
    pages = [PanelPage(**p) for p in (doc.get("pages") or [])]
    trailer = None
    if doc.get("trailer"):
        trailer = TrailerProject(**doc["trailer"])

    return ProjectResponse(
        id=str(project_id),
        title=doc.get("title", ""),
        status=ProjectStatus(doc.get("status", "created")),
        output_mode=doc.get("output_mode", "comic"),
        director_style=doc.get("director_style"),
        script_format=doc.get("script_format", "freeform"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        parsed_script=parsed,
        characters=characters,
        pages=pages,
        trailer=trailer,
    )


# ── Create ──────────────────────────────────────────────────────────

async def create_project(project: ProjectCreate) -> ProjectResponse:
    project_id = _new_id()
    now = _now()

    doc = {
        "project_id": project_id,
        "title": project.title,
        "script": project.script,
        "script_format": project.script_format.value,
        "output_mode": project.output_mode.value,
        "director_style": project.director_style,
        "status": ProjectStatus.CREATED.value,
        "created_at": now,
        "updated_at": now,
        "parsed_script": None,
        "characters": [],
        "pages": [],
        "trailer": None,
    }

    col = get_collection()
    if col is not None:
        doc["_id"] = project_id  # Use project_id as MongoDB _id for simplicity
        await col.insert_one(doc)
        logger.info(f"📝 Created project {project_id} in MongoDB")
    else:
        _save_json(project_id, doc)
        logger.info(f"📝 Created project {project_id} in JSON")

    return ProjectResponse(
        id=project_id,
        title=project.title,
        status=ProjectStatus.CREATED,
        output_mode=project.output_mode,
        director_style=project.director_style,
        script_format=project.script_format,
        created_at=now,
        updated_at=now,
    )


# ── Read ────────────────────────────────────────────────────────────

async def get_project(project_id: str) -> Optional[ProjectResponse]:
    col = get_collection()
    if col is not None:
        doc = await col.find_one({"project_id": project_id})
        if not doc:
            return None
        return _doc_to_response(doc)
    else:
        data = _load_json(project_id)
        if not data:
            return None
        data["project_id"] = project_id
        return _doc_to_response(data)


async def get_project_raw(project_id: str) -> Optional[dict]:
    col = get_collection()
    if col is not None:
        doc = await col.find_one({"project_id": project_id})
        if not doc:
            return None
        doc["id"] = str(doc["project_id"])
        doc.pop("_id", None)
        return doc
    else:
        data = _load_json(project_id)
        if not data:
            return None
        data["id"] = project_id
        return data


async def list_projects(limit: int = 50) -> list[ProjectResponse]:
    col = get_collection()
    if col is not None:
        cursor = col.find().sort("created_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            results.append(_doc_to_response(doc))
        return results
    else:
        items = _list_json(limit)
        results = []
        for pid, data in items:
            data["project_id"] = pid
            results.append(_doc_to_response(data))
        return results


# ── Update ──────────────────────────────────────────────────────────

async def update_project(project_id: str, update: dict) -> None:
    """Update specific fields of a project. Only touches the fields you pass."""
    update["updated_at"] = _now()

    col = get_collection()
    if col is not None:
        # Remove None values for $set (use $unset for explicit nulls)
        set_fields = {k: v for k, v in update.items() if v is not None}
        unset_fields = {k: "" for k, v in update.items() if v is None}

        ops = {}
        if set_fields:
            ops["$set"] = set_fields
        if unset_fields:
            ops["$unset"] = unset_fields

        if ops:
            await col.update_one({"project_id": project_id}, ops)
    else:
        data = _load_json(project_id)
        if data:
            data.update(update)
            _save_json(project_id, data)


async def update_project_status(project_id: str, status) -> None:
    status_val = status.value if hasattr(status, "value") else status
    await update_project(project_id, {"status": status_val})


async def save_parsed_script(project_id: str, parsed: ParsedScript) -> None:
    await update_project(project_id, {
        "parsed_script": parsed.model_dump(),
        "status": ProjectStatus.PARSED.value,
    })


async def save_characters(project_id: str, characters: list[CharacterSheet]) -> None:
    await update_project(project_id, {
        "characters": [c.model_dump() for c in characters],
    })


async def save_pages(project_id: str, pages: list[PanelPage]) -> None:
    await update_project(project_id, {
        "pages": [p.model_dump() for p in pages],
    })


async def save_trailer(project_id: str, trailer: TrailerProject) -> None:
    await update_project(project_id, {
        "trailer": trailer.model_dump(),
    })


# ── Delete ──────────────────────────────────────────────────────────

async def delete_project(project_id: str) -> bool:
    col = get_collection()
    if col is not None:
        result = await col.delete_one({"project_id": project_id})
        return result.deleted_count > 0
    else:
        return _delete_json(project_id)


# ── Migration helpers ───────────────────────────────────────────────

async def migrate_from_firestore():
    """One-time migration: pull all projects from Firestore into MongoDB."""
    try:
        from google.cloud import firestore
        fs_client = firestore.AsyncClient(
            project=settings.google_cloud_project,
            database=settings.firestore_database,
        )
        col = get_collection()
        if col is None:
            logger.error("Cannot migrate: MongoDB not available")
            return

        count = 0
        async for doc in fs_client.collection("projects").stream():
            data = doc.to_dict()
            data["project_id"] = doc.id
            data["_id"] = doc.id

            # Upsert to avoid duplicates
            await col.replace_one(
                {"project_id": doc.id},
                data,
                upsert=True,
            )
            count += 1
            logger.info(f"  Migrated: {doc.id} ({data.get('title', '?')})")

        logger.info(f"✅ Migrated {count} projects from Firestore to MongoDB")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)


# ── Indexes (run once on startup) ──────────────────────────────────

async def ensure_indexes():
    """Create MongoDB indexes for fast queries."""
    col = get_collection()
    if col is None:
        return
    await col.create_index("project_id", unique=True)
    await col.create_index("created_at")
    await col.create_index("status")
    logger.info("📇 MongoDB indexes ensured")


# ── Lazy init — get_collection() calls _init_storage() on first use ──
