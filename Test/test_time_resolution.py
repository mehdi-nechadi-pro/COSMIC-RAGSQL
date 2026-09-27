from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from time_utils import TimeRequest, resolve_time_request


def test_resolve_local_time_to_utc_handles_tonight():
    now_local = datetime(2026, 9, 24, 18, 30, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_time_request(
        TimeRequest(type="relatif", value="ce soir"),
        "Europe/Paris",
        now_local.astimezone(ZoneInfo("UTC")),
    )
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == 20
    assert local.date() == now_local.date()


def test_resolve_local_time_to_utc_handles_demain_a_20h():
    now_local = datetime(2026, 9, 24, 22, 30, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_time_request(
        TimeRequest(type="relatif", value="demain à 20h"),
        "Europe/Paris",
        now_local.astimezone(ZoneInfo("UTC")),
    )
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == 20
    assert local.date() == (now_local.date() + timedelta(days=1))


def test_resolve_local_time_to_utc_handles_now():
    now_local = datetime(2026, 9, 24, 10, 15, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_time_request(
        TimeRequest(type="maintenant"),
        "Europe/Paris",
        now_local.astimezone(ZoneInfo("UTC")),
    )
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == now_local.hour
    assert local.minute == now_local.minute


def test_resolve_time_request_handles_explicit_local_hour():
    now_utc = datetime(2026, 9, 25, 12, 0, tzinfo=ZoneInfo("UTC"))
    result = resolve_time_request(
        TimeRequest(type="explicit", value="22h"),
        "Europe/Paris",
        now_utc,
    )

    local = result.astimezone(ZoneInfo("Europe/Paris"))
    assert local.hour == 22
    assert local.date() == now_utc.astimezone(ZoneInfo("Europe/Paris")).date()
