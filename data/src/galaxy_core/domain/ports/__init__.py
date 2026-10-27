"""Domain 端口 — Protocol-based 接口契约."""

from galaxy_core.domain.ports.calendar_provider import CalendarProviderPort
from galaxy_core.domain.ports.calendar_store import CalendarStorePort
from galaxy_core.domain.ports.exchange_index_provider import (
    ExchangeIndexProviderPort,
)
from galaxy_core.domain.ports.exchange_index_store import ExchangeIndexStorePort
from galaxy_core.domain.ports.financial_data_provider import FinancialDataProviderPort
from galaxy_core.domain.ports.financial_data_store import FinancialDataStorePort
from galaxy_core.domain.ports.fund_flow_provider import FundFlowProviderPort
from galaxy_core.domain.ports.industry_index_provider import (
    IndustryIndexProviderPort,
)
from galaxy_core.domain.ports.industry_index_store import IndustryIndexStorePort
from galaxy_core.domain.ports.kline_provider import KlineProviderPort
from galaxy_core.domain.ports.kline_store import KlineStorePort
from galaxy_core.domain.ports.reference_provider import ReferenceProviderPort

__all__ = [
    "CalendarProviderPort",
    "CalendarStorePort",
    "ExchangeIndexProviderPort",
    "ExchangeIndexStorePort",
    "FinancialDataProviderPort",
    "FinancialDataStorePort",
    "FundFlowProviderPort",
    "IndustryIndexProviderPort",
    "IndustryIndexStorePort",
    "KlineProviderPort",
    "KlineStorePort",
    "ReferenceProviderPort",
]
