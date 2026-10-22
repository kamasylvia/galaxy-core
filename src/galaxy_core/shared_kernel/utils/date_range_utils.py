"""向后兼容 re-export — 日期范围合并已移至 domain.date_range.merger."""

from galaxy_core.domain.date_range.merger import merge_dates_to_ranges

__all__ = ["merge_dates_to_ranges"]
