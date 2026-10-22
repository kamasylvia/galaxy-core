"""回归测试 — adapter index-pattern 对齐(AGENTS.md 2026-06-17 bug 3).

2026-06-17 审计发现 ExchangeIndexProviderAdapter.get_index_code_list 错误地
reset_index() 后找列,但 SDK code 在 df.index。修复后改取 df.index,与
reference_provider_adapter.py:173 一致。

本回归断言:
1. reference_provider_adapter + exchange_index_provider 仍用 df.index 模式
2. Phase 02 akshare_fund_flow_adapter 不含列式 code 提取
   (thin to_thread wrapper,code 提取在 job 层)
   注:2026-06-19 范围修订后 baostock 整源删,相关断言移除。

注意:fundflow_sync_job 的 `df.reset_index() if "MARKET_CODE" not in df.columns`
是防御性条件 reset,不是 bug 模式,不 flag。
"""

from pathlib import Path

SRC_ROOT = Path("src/galaxy_core")
REF_ADAPTER = SRC_ROOT / "amazing_data/api/adapters/reference_provider_adapter.py"
EXCHANGE_ADAPTER = SRC_ROOT / "amazing_data/api/adapters/exchange_index_provider_adapter.py"
AKSHARE_ADAPTER = SRC_ROOT / "third_party/akshare/adapters/akshare_fund_flow_adapter.py"


class TestReferenceAdapterIndexPattern:
    """reference_provider_adapter 是 canonical index-pattern 实现."""

    def test_reference_uses_df_index(self):
        """reference_provider_adapter.get_stock_list 用 df.index.tolist()."""
        src = REF_ADAPTER.read_text()
        # canonical pattern per AGENTS.md 2026-06-17
        assert "df.index.tolist()" in src, (
            "reference_provider_adapter 必须用 df.index.tolist() — "
            "这是 AGENTS.md bug 3 的 canonical 正确写法"
        )


class TestExchangeIndexAdapterIndexPattern:
    """exchange_index_provider_adapter 应对齐 reference 模式(bug 3 已修)."""

    def test_exchange_uses_df_index(self):
        """exchange_index_provider.get_index_code_list 用 df.index."""
        src = EXCHANGE_ADAPTER.read_text()
        # 修复后应含 df.index 模式(reset_index + 列名查找 = bug 模式)
        assert "df.index" in src, (
            "exchange_index_provider 必须用 df.index — bug 3 修复点"
        )


class TestPhase02AdaptersNoColumnCodeAccess:
    """Phase 02 akshare adapter 不含列式 code 提取.

    akshare_fund_flow_adapter 是 thin asyncio.to_thread wrapper,直接返 DataFrame;
    code 提取在 job 层(_df_to_<X>_records),不经 adapter。这样避免 adapter 重复 bug 3。

    注:2026-06-19 范围修订后 baostock 整源删,相关断言移除。
    """

    def test_akshare_adapter_no_column_code_access(self):
        src = AKSHARE_ADAPTER.read_text()
        assert "df['code']" not in src, "akshare adapter 禁止 df['code'] 列式访问"
        assert 'df["code"]' not in src, 'akshare adapter 禁止 df["code"] 列式访问'
        assert "df.loc[:, 'code']" not in src, "akshare adapter 禁止 loc 列式 code"

    def test_baostock_adapter_deleted(self):
        """范围修订回归:baostock adapter 文件应已删."""
        baostock_adapter = SRC_ROOT / "third_party/baostock/adapters/baostock_valuation_adapter.py"
        assert not baostock_adapter.exists(), (
            f"{baostock_adapter} 应已删(baostock 整源删, 2026-06-19 范围修订)"
        )


class TestJobLayerDefensiveResetNotFlagged:
    """fundflow_sync_job 的防御性 reset_index(if MARKET_CODE not in columns)
    不是 bug 3 模式 — 它是条件 reset(列在则不 reset),与无条件 reset_index 后
    找列名的 bug 不同。本测试确认该模式存在且合理。
    """

    def test_fundflow_job_conditional_reset_exists(self):
        """fundflow_sync_job 含防御性条件 reset(market_summary/detail)."""
        src = (
            SRC_ROOT
            / "application/scheduler/jobs/fundflow_sync_job.py"
        ).read_text()
        # 防御模式:reset_index() if "<COL>" not in df.columns
        assert 'not in df.columns' in src or "not in df.columns" in src, (
            "fundflow_job 应有防御性条件 reset(MARKET_CODE/TRADE_DATE 列在则不 reset)"
        )
