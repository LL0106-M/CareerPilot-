from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_ACTION_PATTERN = re.compile(
    r"提醒我|加到日历|加入日历|添加到日历|创建日程|添加日程|安排日程"
)
_NEGATED_ACTION_PATTERN = re.compile(
    r"(?:不要|不用|别|取消).{0,8}(?:提醒|日历|日程)|"
    r"(?:提醒|日历|日程).{0,8}(?:不要|不用|取消)"
)
_URL_PATTERN = re.compile(r"https://[^\s，。；;]+")
_REMINDER_PATTERN = re.compile(r"提前\s*(\d+)\s*(分钟|小时|天)(?:提醒)?")
_DATE_PATTERN = re.compile(
    r"(?P<relative>今天|明天|后天)|(?P<week>(?:周|星期)[一二三四五六日天])|"
    r"(?P<iso>\d{4}-\d{1,2}-\d{1,2})"
)
_TIME_PATTERN = re.compile(
    r"(?P<period>上午|下午|晚上|中午|早上)?\s*"
    r"(?P<hour>\d{1,2}|[一二三四五六七八九十两]+)"
    r"(?:[:：点时](?P<minute>\d{1,2})?分?)"
)
_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}
_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_CHINA_TIME = timezone(timedelta(hours=8))


@dataclass(frozen=True, slots=True)
class ParsedCalendarRequest:
    title: str
    start_at: datetime
    end_at: datetime
    reminder_minutes: int | None = None
    meeting_url: str | None = None


def parse_calendar_request(
    message: str,
    *,
    now: datetime | None = None,
) -> ParsedCalendarRequest | None:
    """Parse only explicit, unambiguous calendar write requests."""

    if not _ACTION_PATTERN.search(message) or _NEGATED_ACTION_PATTERN.search(message):
        return None
    # “下周三” currently needs a dedicated week-offset parser. Do not silently
    # degrade it to this week's Wednesday.
    if "下周" in message or "下星期" in message:
        return None
    reference = now or datetime.now(_CHINA_TIME)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=_CHINA_TIME)
    date_match = _DATE_PATTERN.search(message)
    if date_match is None:
        return None

    time_match = _TIME_PATTERN.search(message, date_match.end())
    if time_match is None:
        return None
    try:
        event_date = _resolve_date(date_match, reference)
        hour, minute = _resolve_time(time_match)
        start_at = reference.replace(
            year=event_date.year,
            month=event_date.month,
            day=event_date.day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
    except (KeyError, OverflowError, ValueError):
        return None
    if start_at <= reference and date_match.group("week"):
        start_at += timedelta(days=7)

    reminder_match = _REMINDER_PATTERN.search(message)
    reminder_minutes = _reminder_minutes(reminder_match)
    url_match = _URL_PATTERN.search(message)
    meeting_url = url_match.group(0) if url_match else None
    title = _extract_title(message, date_match, time_match, reminder_match, url_match)
    if not title:
        return None
    return ParsedCalendarRequest(
        title=title,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
        reminder_minutes=reminder_minutes,
        meeting_url=meeting_url,
    )


def _resolve_date(match: re.Match[str], reference: datetime) -> datetime:
    if relative := match.group("relative"):
        offset = {"今天": 0, "明天": 1, "后天": 2}[relative]
        return reference + timedelta(days=offset)
    if week := match.group("week"):
        weekday = _WEEKDAYS[week[-1]]
        return reference + timedelta(days=(weekday - reference.weekday()) % 7)
    return datetime.strptime(match.group("iso"), "%Y-%m-%d").replace(tzinfo=reference.tzinfo)


def _resolve_time(match: re.Match[str]) -> tuple[int, int]:
    raw_hour = match.group("hour")
    hour = int(raw_hour) if raw_hour.isdigit() else _CHINESE_NUMBERS.get(raw_hour, 9)
    minute = int(match.group("minute") or 0)
    period = match.group("period") or ""
    if period in {"下午", "晚上"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if hour > 23 or minute > 59:
        raise ValueError("invalid time")
    return hour, minute


def _reminder_minutes(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    amount = int(match.group(1))
    return amount * {"分钟": 1, "小时": 60, "天": 1440}[match.group(2)]


def _extract_title(
    message: str,
    date_match: re.Match[str],
    time_match: re.Match[str] | None,
    reminder_match: re.Match[str] | None,
    url_match: re.Match[str] | None,
) -> str:
    title = _ACTION_PATTERN.sub("", message)
    for match in (date_match, time_match, reminder_match, url_match):
        if match is not None:
            title = title.replace(match.group(0), "")
    title = re.sub(r"会议链接|链接|，|。|；|;|：|:", " ", title)
    return re.sub(r"\s+", " ", title).strip()
