from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models import WeekType


def current_local_date() -> date:
    """Текущая календарная дата в часовом поясе учебного расписания."""
    return datetime.now(ZoneInfo(settings.timezone)).date()


def week_type_for_date(target: date) -> WeekType:
    """Белая или зелёная неделя для даты.

    Отсчёт от понедельника недели, в которую попадает SEMESTER_START;
    эта неделя считается белой, дальше цвета чередуются.
    """
    anchor = settings.semester_start
    anchor_monday = anchor - timedelta(days=anchor.isoweekday() - 1)
    target_monday = target - timedelta(days=target.isoweekday() - 1)
    weeks_passed = (target_monday - anchor_monday).days // 7
    return WeekType.white if weeks_passed % 2 == 0 else WeekType.green
