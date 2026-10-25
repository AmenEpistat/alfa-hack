"""Internal five-calendar-year history window, resolved once per request in Moscow time."""
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

HISTORY_YEARS = 5
REQUEST_TIMEZONE = "Europe/Moscow"


def request_day():
    return datetime.now(ZoneInfo(REQUEST_TIMEZONE)).date()


@dataclass(frozen=True)
class HistoryWindow:
    start: date
    end: date

    def metadata(self):
        return {"policy": "last_five_years", "years": HISTORY_YEARS, "timezone": REQUEST_TIMEZONE,
                "start": self.start.isoformat(), "end": self.end.isoformat()}


def history_window():
    end = request_day()
    try:
        start = end.replace(year=end.year - HISTORY_YEARS)
    except ValueError:  # February 29 -> February 28 in the target year.
        start = end.replace(year=end.year - HISTORY_YEARS, day=28)
    return HistoryWindow(start, end)
