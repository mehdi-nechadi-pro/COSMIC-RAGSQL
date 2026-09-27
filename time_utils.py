from datetime import datetime, timezone, timedelta
import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from dateutil import parser


class TimeRequest(BaseModel):
    type: Literal[
        "maintenant",
        "explicit",
        "relatif",
        "astronomical",
    ]
    value: str | None = None


def default_time_request() -> TimeRequest:
    return TimeRequest(type="maintenant", value=None)


def resolve_relative_time_request(
    value: str,
    timezone_name: str,
    now_local: datetime,
) -> datetime:

    normalized = value.strip().lower()
    print(f"[TIME] resolve_relative_time_request: value={normalized!r}")

    target_tz = ZoneInfo(timezone_name)

    if now_local.tzinfo is None:
        raise ValueError("now_local doit être timezone-aware.")

    now_local = now_local.astimezone(target_tz)

    tomorrow_match = re.search(
        r"(?:demain|tomorrow)\s*(?:à|a|at)?\s*(\d{1,2})(?:\s*(?:h|:|heure)\s*(\d{0,2}))?",
        normalized,
    )
    if tomorrow_match:
        print("[TIME] Branche relative: demain avec heure explicite")
        hour = int(tomorrow_match.group(1))
        minute = int(tomorrow_match.group(2) or 0)
        if hour > 23 or minute > 59:
            raise ValueError("Heure locale invalide")
        candidate = (now_local + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return candidate.astimezone(timezone.utc)

    explicit_match = re.search(
        r"(?:ce soir|tonight)?\s*(?:à|a|at)\s*(\d{1,2})(?:\s*(?:h|:|heure)\s*(\d{0,2}))?",
        normalized,
    )
    if explicit_match:
        print("[TIME] Branche relative: heure explicite aujourd'hui/ce soir")
        hour = int(explicit_match.group(1))
        minute = int(explicit_match.group(2) or 0)
        if hour > 23 or minute > 59:
            raise ValueError("Heure locale invalide")
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local and normalized.startswith(("ce soir", "tonight")):
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    # Maintenant
    if normalized in {"maintenant","maintenant même","now","right now"}:
        print("[TIME] Branche relative: maintenant")
        return now_local.astimezone(timezone.utc)

    # Ce soir
    if normalized in {"ce soir","tonight"}:
        print("[TIME] Branche relative: ce soir (20:00)")
        candidate = now_local.replace(hour=20, minute=0, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    # Demain matin
    if normalized in {"demain matin","tomorrow morning"}:
        print("[TIME] Branche relative: demain matin (06:00)")
        candidate = (now_local + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    # Demain
    if normalized in {"demain","tomorrow"}:
        print("[TIME] Branche relative: demain (12:00)")
        candidate = (now_local + timedelta(days=1)).replace( hour=12, minute=0, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    # Cas plus complexes :
    # "dans deux heures", "dans 30 minutes", etc.
    print("[TIME] Branche relative: délégation à resolve_local_time_to_utc")
    return resolve_local_time_to_utc(timezone_name, normalized, now_local)


def resolve_time_request(time_request: TimeRequest, timezone_name: str, now_utc: datetime ) -> datetime:
    
    if now_utc.tzinfo is None:
        raise ValueError("now_utc doit être timezone-aware.")

    now_utc = now_utc.astimezone(timezone.utc)

    target_tz = ZoneInfo(timezone_name)
    now_local = now_utc.astimezone(target_tz)

    request_type = time_request.type
    value = (time_request.value or "").strip()
    print(
        f"[TIME] resolve_time_request: type={request_type!r}, "
        f"value={value!r}, timezone={timezone_name!r}"
    )

    # Maintenant
    if request_type == "maintenant":
        print("[TIME] Branche TimeRequest: maintenant")
        return now_utc

    # Heure/date explicite
    if request_type == "explicit":
        print("[TIME] Branche TimeRequest: explicit")
        if not value:
            raise ValueError("Un TimeRequest explicit doit avoir une value.")

        return resolve_local_time_to_utc(timezone_name, value, now_local)

    # Expression relative
    if request_type == "relatif":
        print("[TIME] Branche TimeRequest: relatif")
        if not value:
            raise ValueError("Un TimeRequest relatif doit avoir une value.")
        
        return resolve_relative_time_request(value, timezone_name, now_local)

    # Événement astronomique
    if request_type == "astronomical":
        print("[TIME] Branche TimeRequest: astronomical non supportée")
        raise ValueError(f"Événement astronomique non supporté : {value}")

    print(f"[TIME] Branche TimeRequest inconnue: {request_type!r}")
    raise ValueError(
        f"Type de TimeRequest inconnu : {request_type}"
    )


TIME_TOKEN_RULES = {
    "maintenant": None,
    "now": None,
    "ce soir": "20:00",
    "tonight": "20:00",
    "demain matin": "06:00",
    "tomorrow morning": "06:00",
}

def resolve_local_time_to_utc(timezone_name: str, user_input_str: str = "", now_local: datetime | None = None) -> datetime:
    """
    Centralise la conversion d'une heure locale humaine vers UTC.
    Le LLM ne doit plus fournir le datetime final ; il fournit seulement un contexte.
    """
    target_tz = ZoneInfo(timezone_name) if timezone_name else ZoneInfo("UTC")
    if now_local is None:
        now_local = datetime.now(target_tz)

    clean_str = (user_input_str or "").strip()
    print(
        f"[TIME] resolve_local_time_to_utc: input={clean_str!r}, "
        f"timezone={timezone_name!r}"
    )
    if clean_str == "":
        print("[TIME] Branche locale: entrée vide, heure actuelle")
        return now_local.astimezone(ZoneInfo("UTC"))

    normalized = clean_str.lower().strip()
    for key, value in TIME_TOKEN_RULES.items():
        if normalized == key:
            print(f"[TIME] Branche locale: token prédéfini {key!r}")
            if value is None:
                return now_local.astimezone(ZoneInfo("UTC"))
            hh, mm = map(int, value.split(":"))
            candidate = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            return candidate.astimezone(ZoneInfo("UTC"))

    match = re.search(r"(demain|tomorrow).*?(\d{1,2})\s*(?:h|heure|:)?\s*(\d{0,2})", normalized)
    if match:
        print("[TIME] Branche locale: demain avec heure détectée par regex")
        hour = int(match.group(2))
        minute = int(match.group(3)) if match.group(3) else 0
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(ZoneInfo("UTC"))

    explicit_match = re.fullmatch(
        r"(?:aujourd['’]hui\s+|today\s+)?(?:à|a|at)\s*(\d{1,2})(?:\s*(?:h|:|heure)\s*(\d{0,2}))?",
        normalized,
    )
    if explicit_match:
        print("[TIME] Branche locale: heure explicite détectée par regex")
        hour = int(explicit_match.group(1))
        minute = int(explicit_match.group(2) or 0)
        if hour > 23 or minute > 59:
            raise ValueError("Heure locale invalide")
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate.astimezone(ZoneInfo("UTC"))

    try:
        parsed = parser.parse(clean_str, default=now_local)
        print("[TIME] Branche locale: dateutil.parser")
        if parsed.tzinfo is not None:
            return parsed.astimezone(ZoneInfo("UTC"))
        local_dt = parsed.replace(tzinfo=target_tz)
        return local_dt.astimezone(ZoneInfo("UTC"))
    except (ValueError, TypeError):
        print("[TIME] Branche locale: échec du parsing, heure actuelle utilisée")
        return now_local.astimezone(ZoneInfo("UTC"))


def get_utc_date(timezone, user_input_str: str = "") -> datetime:
    """Compatibilité: garde l'ancien nom et délègue au système unifié."""
    tz_name = timezone or "UTC"
    now_local = datetime.now(ZoneInfo(tz_name)) if tz_name != "UTC" else datetime.now(ZoneInfo("UTC"))
    return resolve_local_time_to_utc(tz_name, user_input_str, now_local)