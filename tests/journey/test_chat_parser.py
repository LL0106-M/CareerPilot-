from datetime import datetime, timedelta, timezone

from careerpilot.journey.chat_parser import parse_calendar_request

CHINA_TIME = timezone(timedelta(hours=8))


def test_parser_extracts_relative_time_reminder_and_tencent_meeting_url() -> None:
    now = datetime(2026, 10, 29, 9, 0, tzinfo=CHINA_TIME)

    parsed = parse_calendar_request(
        "提醒我明天下午3点参加腾讯产品二面，提前30分钟提醒，会议链接 "
        "https://meeting.tencent.com/dm/abc",
        now=now,
    )

    assert parsed is not None
    assert parsed.title == "参加腾讯产品二面"
    assert parsed.start_at.isoformat() == "2026-10-30T15:00:00+08:00"
    assert parsed.end_at.isoformat() == "2026-10-30T16:00:00+08:00"
    assert parsed.reminder_minutes == 30
    assert parsed.meeting_url == "https://meeting.tencent.com/dm/abc"


def test_parser_ignores_calendar_discussion_without_a_write_request() -> None:
    now = datetime(2026, 10, 29, 9, 0, tzinfo=CHINA_TIME)

    assert parse_calendar_request("腾讯会议好用吗", now=now) is None


def test_parser_does_not_guess_when_an_explicit_request_has_no_date() -> None:
    now = datetime(2026, 10, 29, 9, 0, tzinfo=CHINA_TIME)

    assert parse_calendar_request("提醒我准备面试", now=now) is None


def test_parser_rejects_negation_ambiguous_week_and_missing_time() -> None:
    now = datetime(2026, 10, 29, 9, 0, tzinfo=CHINA_TIME)

    assert parse_calendar_request("不要提醒我明天下午3点面试", now=now) is None
    assert parse_calendar_request("提醒我下周三下午3点面试", now=now) is None
    assert parse_calendar_request("提醒我明天面试", now=now) is None


def test_parser_returns_none_for_invalid_calendar_values() -> None:
    now = datetime(2026, 10, 29, 9, 0, tzinfo=CHINA_TIME)

    assert parse_calendar_request("提醒我2026-02-30下午3点面试", now=now) is None
    assert parse_calendar_request("提醒我明天下午25点面试", now=now) is None
