"""AmazingData OpenBB Platform Provider (DB-backed).

Reads from local TimescaleDB ``obb_equity_historical`` view
(migration 29), NOT from AmazingData SDK directly.
"""

from openbb_core.provider.abstract.provider import Provider

from openbb_provider_amazingdata.models.equity_historical import (
    AmazingDataEquityHistoricalFetcher,
)
from openbb_provider_amazingdata.models.statements import (
    AmazingDataBalanceSheetFetcher,
    AmazingDataCashFlowFetcher,
    AmazingDataIncomeStatementFetcher,
)

provider = Provider(
    name="amazingdata",
    description="DB-backed A-share provider (local TimescaleDB).",
    website="https://github.com/kamasylvia/galaxy-core",
    fetcher_dict={
        "EquityHistorical": AmazingDataEquityHistoricalFetcher,
        "IncomeStatement": AmazingDataIncomeStatementFetcher,
        "BalanceSheet": AmazingDataBalanceSheetFetcher,
        "CashFlowStatement": AmazingDataCashFlowFetcher,
    },
)
