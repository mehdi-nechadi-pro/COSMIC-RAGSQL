from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astropy_function import resolve_local_time_to_utc


def test_resolve_local_time_to_utc_handles_tonight():
    now_local = datetime(2026, 9, 24, 18, 30, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_local_time_to_utc("Europe/Paris", "ce soir", now_local)
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == 20
    assert local.date() == now_local.date()


def test_resolve_local_time_to_utc_handles_demain_a_20h():
    now_local = datetime(2026, 9, 24, 22, 30, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_local_time_to_utc("Europe/Paris", "demain à 20h", now_local)
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == 20
    assert local.date() == (now_local.date() + timedelta(days=1))


def test_resolve_local_time_to_utc_handles_now():
    now_local = datetime(2026, 9, 24, 10, 15, tzinfo=ZoneInfo("Europe/Paris"))
    result = resolve_local_time_to_utc("Europe/Paris", "maintenant", now_local)
    local = result.astimezone(ZoneInfo("Europe/Paris"))

    assert local.hour == now_local.hour
    assert local.minute == now_local.minute
