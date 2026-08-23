"""退休测算核心逻辑。

计算依据：《国务院关于渐进式延迟法定退休年龄的办法》
（2024 年 9 月 13 日通过，自 2025 年 1 月 1 日起施行）

- 男职工：原 60 周岁，每 4 个月延迟 1 个月，逐步延迟至 63 周岁；
- 女干部（原法定退休年龄 55 周岁）：每 4 个月延迟 1 个月，逐步延迟至 58 周岁；
- 女工人（原法定退休年龄 50 周岁）：每 2 个月延迟 1 个月，逐步延迟至 55 周岁。

注意：本模块只按“法定退休年龄”测算退休日期，不涉及缴费年限、
特殊工种提前退休等情形，结果仅供参考。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

__all__ = [
    "RetirementResult",
    "WorkerType",
    "calculate_retirement",
    "parse_birth_date",
    "parse_worker_type",
]


class WorkerType(str, Enum):
    """职工类型。"""

    MALE = "男职工"
    FEMALE_WORKER = "女工人"
    FEMALE_CADRE = "女干部"


@dataclass(frozen=True)
class RetirementResult:
    """退休测算结果。"""

    birth_date: date
    worker_type: WorkerType
    original_retirement_age: int
    new_retirement_age_years: int
    new_retirement_age_months: int
    delay_months: int
    retirement_date: date
    remaining_days: int

    @property
    def new_retirement_age(self) -> str:
        """改革后退休年龄，例如：60岁、62岁10个月、63岁。"""

        if self.delay_months == 0:
            return f"{self.original_retirement_age}岁"
        if self.new_retirement_age_months == 0:
            return f"{self.new_retirement_age_years}岁"
        return f"{self.new_retirement_age_years}岁{self.new_retirement_age_months}个月"

    @property
    def is_retired(self) -> bool:
        """是否已经超过退休日期。"""

        return self.remaining_days < 0


@dataclass(frozen=True)
class _Policy:
    """某一类职工的延迟退休政策参数。"""

    worker_type: WorkerType
    original_age: int
    max_age: int
    start_year: int
    start_month: int
    pace_months: int


_POLICIES: tuple[_Policy, ...] = (
    _Policy(WorkerType.MALE, 60, 63, 1965, 1, 4),
    _Policy(WorkerType.FEMALE_CADRE, 55, 58, 1970, 1, 4),
    _Policy(WorkerType.FEMALE_WORKER, 50, 55, 1975, 1, 2),
)

_POLICY_BY_TYPE: dict[WorkerType, _Policy] = {
    policy.worker_type: policy for policy in _POLICIES
}


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _add_months(d: date, months: int) -> date:
    """在日期上增加若干个月，超出当月天数的部分按月末截断。"""

    total = d.year * 12 + (d.month - 1) + months
    year, zero_based_month = divmod(total, 12)
    month = zero_based_month + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def calculate_retirement(
    birth_date: date,
    worker_type: WorkerType,
    today: date | None = None,
) -> RetirementResult:
    """根据出生日期和职工类型计算退休日期与剩余天数。

    延迟月数的计算方式：从政策启动月份起，每经过
    ``pace_months`` 个月出生的人，延迟月数增加 1 个月，
    直到达到政策规定的最大延迟月数。
    """

    policy = _POLICY_BY_TYPE[worker_type]
    today = today or date.today()

    offset_months = (birth_date.year - policy.start_year) * 12 + (
        birth_date.month - policy.start_month
    )
    max_delay = (policy.max_age - policy.original_age) * 12

    if offset_months < 0:
        delay_months = 0
    else:
        delay_months = min(max_delay, offset_months // policy.pace_months + 1)

    retirement_date = _add_months(
        birth_date, policy.original_age * 12 + delay_months
    )
    return RetirementResult(
        birth_date=birth_date,
        worker_type=worker_type,
        original_retirement_age=policy.original_age,
        new_retirement_age_years=policy.original_age + delay_months // 12,
        new_retirement_age_months=delay_months % 12,
        delay_months=delay_months,
        retirement_date=retirement_date,
        remaining_days=(retirement_date - today).days,
    )


_FULL_DATE = re.compile(
    r"^(?P<year>\d{4})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})日?$"
)
_YEAR_MONTH = re.compile(r"^(?P<year>\d{4})[-/.年](?P<month>\d{1,2})月?$")
_MONTH_DAY = re.compile(r"^(?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})日?$")


def parse_birth_date(text: str) -> date | None:
    """解析出生日期，支持多种常见格式。

    支持：1995-01-01、1995/1/1、1995年1月1日、1995年1月、
    6月1日（默认当前年份）。
    """

    text = text.strip()
    for pattern in (_FULL_DATE, _YEAR_MONTH, _MONTH_DAY):
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groupdict()
        try:
            if "day" in groups:
                if "year" in groups:
                    birth = date(
                        int(groups["year"]), int(groups["month"]), int(groups["day"])
                    )
                else:
                    birth = date(
                        date.today().year, int(groups["month"]), int(groups["day"])
                    )
            else:
                birth = date(int(groups["year"]), int(groups["month"]), 1)
        except ValueError:
            continue
        return birth
    return None


def parse_worker_type(text: str) -> WorkerType | None:
    """解析职工类型输入。

    仅写“女”时默认按女干部（原 55 周岁）计算，
    需要按工人身份测算请写“女工人”。
    """

    key = text.strip().lower()
    if key in {"男", "男性", "男职工", "male", "m"}:
        return WorkerType.MALE
    if key in {"女工人", "女工", "工人", "女职工"}:
        return WorkerType.FEMALE_WORKER
    if key in {"女", "女性", "女干部", "干部", "管理岗", "female", "f"}:
        return WorkerType.FEMALE_CADRE
    return None
