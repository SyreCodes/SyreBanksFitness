from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tests.test_core_loop import auth, identity


def slot(days_ahead: int, hour: int = 9) -> datetime:
    zone = ZoneInfo("Africa/Kigali")
    day = datetime.now(UTC).astimezone(zone).date() + timedelta(days=days_ahead)
    return datetime.combine(day, time(hour=hour), zone)


def test_calendar_http_range_statuses_booking_and_utc_response(client, db):
    coach = identity(db, "COACH", "Coach")
    member = identity(db, "CLIENT", "Member", coach.id)
    coach_headers, member_headers = auth(client, coach), auth(client, member)
    booked_start, blocked_start = slot(2), slot(3)
    changed = client.patch(
        f"/api/v1/bookings/availability/settings/{coach.id}",
        json={"weekdays": list(range(7)), "hours": [9], "blocked_dates": [blocked_start.date().isoformat()]},
        headers=coach_headers,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["blocked_dates"] == [blocked_start.date().isoformat()]
    bounds = {"start": slot(1, 0).isoformat(), "end": slot(5, 0).isoformat()}
    feed = client.get("/api/v1/bookings/availability", params={**bounds, "include_unavailable": "true"}, headers=member_headers)
    assert feed.status_code == 200, feed.text
    assert feed.json()["timezone"] == "Africa/Kigali"
    assert {item["status"] for item in feed.json()["items"]} >= {"AVAILABLE", "BLOCKED"}
    assert any(item.get("reason") == "BLOCKED_DATE" for item in feed.json()["items"])
    available_only = client.get("/api/v1/bookings/availability", params=bounds, headers=member_headers)
    assert all(item["status"] == "AVAILABLE" for item in available_only.json()["items"])

    booking = client.post("/api/v1/bookings", json={
        "coach_id": coach.id, "starts_at": booked_start.isoformat(),
        "ends_at": (booked_start + timedelta(hours=1)).isoformat(), "type": "consultation",
    }, headers=member_headers)
    assert booking.status_code == 201, booking.text
    assert booking.json()["starts_at"].endswith(("Z", "+00:00"))
    refreshed = client.get("/api/v1/bookings/availability", params={**bounds, "include_unavailable": "true"}, headers=member_headers)
    occupied = next(item for item in refreshed.json()["items"] if item["starts_at"] == booking.json()["starts_at"])
    assert occupied["status"] == "BOOKED"
    assert occupied["booked_by_me"] is True
    assert occupied["booking_id"] == booking.json()["id"]
    listing = client.get("/api/v1/bookings", params=bounds, headers=member_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["starts_at"].endswith(("Z", "+00:00"))


def test_calendar_http_permissions_and_cancellation_cutoff(client, db):
    admin = identity(db, "ADMIN", "Admin")
    coach = identity(db, "COACH", "Coach")
    other_coach = identity(db, "COACH", "Other Coach")
    member = identity(db, "CLIENT", "Member", coach.id)
    admin_headers, coach_headers, member_headers = auth(client, admin), auth(client, coach), auth(client, member)
    url = f"/api/v1/bookings/availability/settings/{coach.id}"
    assert client.patch(url, json={"blocked_dates": []}, headers=member_headers).status_code == 403
    assert client.patch(f"/api/v1/bookings/availability/settings/{other_coach.id}", json={"hours": [10]}, headers=coach_headers).status_code == 403
    assert client.get(url, headers=coach_headers).status_code == 200
    assert client.patch(url, json={"weekdays": list(range(7)), "hours": [9], "cancellation_notice_hours": 168}, headers=admin_headers).status_code == 200
    upcoming = slot(2)
    reservation = client.post("/api/v1/bookings", json={"coach_id": coach.id, "starts_at": upcoming.isoformat(),
        "ends_at": (upcoming + timedelta(hours=1)).isoformat(), "type": "consultation"}, headers=member_headers)
    assert reservation.status_code == 201, reservation.text
    cancel_url = f"/api/v1/bookings/{reservation.json()['id']}"
    too_late = client.patch(cancel_url, json={"status": "CANCELLED"}, headers=member_headers)
    assert too_late.status_code == 409
    assert too_late.json()["error"]["code"] == "CANCELLATION_WINDOW_CLOSED"
    assert client.patch(cancel_url, json={"status": "CANCELLED"}, headers=admin_headers).status_code == 200
    assert client.patch(cancel_url, json={"status": "CANCELLED"}, headers=member_headers).status_code == 200


def test_calendar_http_rejects_invalid_range_and_vacation_booking(client, db):
    coach = identity(db, "COACH", "Coach")
    member = identity(db, "CLIENT", "Member", coach.id)
    coach_headers, member_headers = auth(client, coach), auth(client, member)
    vacation_day = slot(2).date().isoformat()
    updated = client.patch(f"/api/v1/bookings/availability/settings/{coach.id}", json={
        "weekdays": list(range(7)), "hours": [9],
        "vacation_ranges": [{"start_date": vacation_day, "end_date": vacation_day}],
    }, headers=coach_headers)
    assert updated.status_code == 200, updated.text
    wanted = slot(2)
    unavailable = client.post("/api/v1/bookings", json={"coach_id": coach.id, "starts_at": wanted.isoformat(),
        "ends_at": (wanted + timedelta(hours=1)).isoformat(), "type": "consultation"}, headers=member_headers)
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["code"] == "COACH_UNAVAILABLE"
    naive = client.get("/api/v1/bookings/availability", params={"start": "2026-10-01T00:00:00", "end": "2026-10-02T00:00:00Z"}, headers=member_headers)
    assert naive.status_code == 422
    assert naive.json()["error"]["code"] == "INVALID_CALENDAR_RANGE"
    oversized = client.get("/api/v1/bookings/availability", params={
        "start": datetime.now(UTC).isoformat(), "end": (datetime.now(UTC) + timedelta(days=63)).isoformat(),
    }, headers=member_headers)
    assert oversized.status_code == 422
