"""向后兼容 re-export — Interval 枚举已移至 domain.value_objects."""

from galaxy_core.domain.value_objects import Interval

__all__ = ["Interval"]
