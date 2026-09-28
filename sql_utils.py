
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, or_, select, text


ALLOWED_TARGET_FILTER_KEYS = {
    "name",
    "type",
    "constellation",
    "catalogue",
    "magnitude_min",
    "magnitude_max",
    "ra_min",
    "ra_max",
    "dec_min",
    "dec_max",
    "limit",
}

MAX_TARGET_LIMIT = 50
ACTIVE_VISIBILITY_SQL = ""


class TargetFilters(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    constellation: Optional[str] = None
    catalogue: Optional[str] = None
    magnitude_min: Optional[float] = Field(default=None, ge=0.0)
    magnitude_max: Optional[float] = Field(default=None, ge=0.0)
    ra_min: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    ra_max: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    dec_min: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    dec_max: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    limit: int = Field(default=8, ge=1, le=MAX_TARGET_LIMIT)


def validate_target_filters(filters_json: Any) -> Dict[str, Any]:
    if filters_json is None:
        return {"limit": 8}

    if not isinstance(filters_json, dict):
        raise ValueError("filters_json must be a dictionary, not raw SQL text.")

    unknown = set(filters_json.keys()) - ALLOWED_TARGET_FILTER_KEYS
    if unknown:
        raise ValueError(
            f"Unknown target filter(s): {sorted(unknown)}. "
            f"Allowed keys: {sorted(ALLOWED_TARGET_FILTER_KEYS)}"
        )

    prohibited_sql = {"query", "sql", "raw_sql", "statement", "command"}
    if prohibited_sql.intersection(filters_json):
        raise ValueError("Raw SQL payloads are forbidden. Send validated filters only.")

    for key, value in filters_json.items():
        if isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in ["select", "insert", "update", "delete", "drop", "alter", "truncate", "union", "--", ";"]):
                raise ValueError("String values must not contain raw SQL clauses or separators.")
            if any(keyword in lowered for keyword in ["from ", "where ", "join ", "order by", "group by"]):
                raise ValueError("String values must not look like SQL fragments.")

    cleaned = TargetFilters.model_validate(filters_json).model_dump(exclude_none=True)
    if cleaned.get("limit", 8) > MAX_TARGET_LIMIT:
        raise ValueError(f"limit must be <= {MAX_TARGET_LIMIT}")
    return cleaned


def build_targets_query(filters: Dict[str, Any], engine, visibility_sql: Optional[str] = None):
    metadata = MetaData()
    celestial = Table("Celestial", metadata, autoload_with=engine)
    conditions = []
    ra_min = filters.get("ra_min")
    ra_max = filters.get("ra_max")

    for field, value in filters.items():
        if field == "limit":
            continue

        if field in {"ra_min", "ra_max", "dec_min", "dec_max"}:
            continue

        column = getattr(celestial.c, field, None)
        if column is None:
            raise ValueError(f"Unsupported filter field: {field}")

        if field in {"name", "type", "constellation", "catalogue"}:
            conditions.append(column.ilike(f"%{value}%"))
        elif field == "magnitude_min":
            conditions.append(column >= value)
        elif field == "magnitude_max":
            conditions.append(column <= value)

    if ra_min is not None and ra_max is not None and ra_min > ra_max:
        conditions.append(or_(celestial.c.ra >= ra_min, celestial.c.ra <= ra_max))
    else:
        if ra_min is not None:
            conditions.append(celestial.c.ra >= ra_min)
        if ra_max is not None:
            conditions.append(celestial.c.ra <= ra_max)

    if filters.get("dec_min") is not None:
        conditions.append(celestial.c.dec >= filters["dec_min"])
    if filters.get("dec_max") is not None:
        conditions.append(celestial.c.dec <= filters["dec_max"])

    if visibility_sql:
        visibility_sql = visibility_sql.strip()
        if not visibility_sql.endswith("= 1") and not visibility_sql.endswith("=1"):
            visibility_sql = f"({visibility_sql}) = 1"
        conditions.append(text(visibility_sql))

    stmt = select(celestial).where(*conditions).limit(filters.get("limit", 8))
    return stmt
