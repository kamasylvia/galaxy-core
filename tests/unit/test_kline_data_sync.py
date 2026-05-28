"""K 线数据同步服务测试模块.

测试 kline_data_sync_service 的功能，包括：
- 单证券同步
- 批量同步
- 缺失区间分组
- 空查询缓存集成
"""

import unittest
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd

from galaxy_db_sync.database.services.kline_completeness_checker import (
    CompletenessResult,
)


class TestSyncKlineData(unittest.TestCase):
    """单证券同步测试类."""

    def test_sync_kline_data_passes_interval_to_client_wrapper(self):
        """测试同步层调用包装器时使用 interval 参数名，而不是 SDK 的 period."""
        fake_df = pd.DataFrame(
            {"close": [123.45]},
            index=pd.to_datetime(["2017-04-05"]),
        )

        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[(date(2017, 4, 5), date(2017, 4, 7))],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                return_value={"600519.SH": fake_df},
            ) as mock_query_kline,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.infer_security_type",
                return_value="stock",
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_service.save_kline_to_db",
                return_value=1,
            ) as mock_save,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 1)
        mock_query_kline.assert_called_once_with(
            code_list=["600519.SH"],
            begin_date=20170405,
            end_date=20170407,
            interval=10008,
        )
        self.assertEqual(mock_query_kline.call_args.kwargs.get("period"), None)
        mock_save.assert_called_once()

    def test_sync_kline_data_saves_non_empty_result_without_caching_empty_range(self):
        """测试非空 API 结果会正常保存，且不会写入空查询缓存."""
        fake_df = pd.DataFrame(
            {"close": [123.45]},
            index=pd.to_datetime(["2017-04-05"]),
        )

        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[(date(2017, 4, 5), date(2017, 4, 7))],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                return_value={"600519.SH": fake_df},
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.infer_security_type",
                return_value="stock",
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_data_sync_service.save_kline_data",
                return_value=1,
            ) as mock_save,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.record_empty_result"
            ) as mock_record_empty,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 1)
        mock_save.assert_called_once()
        mock_record_empty.assert_not_called()

    def test_sync_kline_data_queries_only_uncached_missing_ranges(self):
        """测试单证券同步仅查询未缓存为空的缺失区间."""
        fake_df = pd.DataFrame(
            {"close": [123.45]},
            index=pd.to_datetime(["2017-04-06"]),
        )

        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[
                        (date(2017, 4, 5), date(2017, 4, 5)),
                        (date(2017, 4, 6), date(2017, 4, 7)),
                    ],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                side_effect=[True, False],
            ) as mock_is_confirmed_empty,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                return_value={"600519.SH": fake_df},
            ) as mock_query_kline,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.infer_security_type",
                return_value="stock",
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_data_sync_service.save_kline_data",
                return_value=1,
            ) as mock_save,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 1)
        self.assertEqual(mock_is_confirmed_empty.call_count, 2)
        mock_query_kline.assert_called_once_with(
            code_list=["600519.SH"],
            begin_date=20170406,
            end_date=20170407,
            interval=10008,
        )
        mock_save.assert_called_once()

    def test_sync_kline_data_does_not_cache_known_sdk_type_error(self):
        """测试已知 SDK TypeError 不会写入空查询缓存."""
        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[(date(2017, 4, 5), date(2017, 4, 7))],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                side_effect=TypeError("'NoneType' object cannot be interpreted as an integer"),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_data_sync_service.save_kline_data"
            ) as mock_save,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.record_empty_result"
            ) as mock_record_empty,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 0)
        mock_save.assert_not_called()
        mock_record_empty.assert_not_called()

    def test_sync_kline_data_records_empty_result_without_saving(self):
        """测试空 API 结果会写入空查询缓存，且不会保存 K 线数据."""
        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.parse_date_to_datetime",
                side_effect=[date(2017, 4, 5), date(2017, 4, 7)],
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_completeness_checker.check",
                return_value=CompletenessResult(
                    is_complete=False,
                    missing_count=3,
                    total_count=3,
                    coverage_ratio=0.0,
                    missing_ranges=[(date(2017, 4, 5), date(2017, 4, 7))],
                    check_method="short_period_trading_day",
                ),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                return_value={"600519.SH": pd.DataFrame()},
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.kline_data_sync_service.save_kline_data"
            ) as mock_save,
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.record_empty_result"
            ) as mock_record_empty,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            synced = kline_data_sync_service.sync_kline_data(
                symbol="600519.SH",
                interval="day",
                start_date="20170405",
                end_date="20170407",
                interval_value=10008,
            )

        self.assertEqual(synced, 0)
        mock_save.assert_not_called()
        mock_record_empty.assert_called_once_with(
            "600519.SH",
            "day",
            date(2017, 4, 5),
            date(2017, 4, 7),
        )


class TestGroupByMissingRanges(unittest.TestCase):
    """缺失区间分组测试类."""

    def test_group_by_missing_ranges_uses_interval_and_skips_confirmed_empty_ranges(self):
        """测试缺失区间分组时使用真实 interval，并跳过已缓存为空的区间."""
        completeness_results = {
            "600519.SH": CompletenessResult(
                is_complete=False,
                missing_count=2,
                total_count=2,
                coverage_ratio=0.0,
                missing_ranges=[
                    (date(2024, 1, 1), date(2024, 1, 31)),
                    (date(2024, 2, 1), date(2024, 2, 29)),
                ],
                check_method="long_period",
            )
        }

        with patch(
            "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
            side_effect=[True, False],
        ) as mock_is_confirmed_empty:
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            grouped = kline_data_sync_service._group_by_missing_ranges(
                completeness_results,
                "month",
            )

        self.assertEqual(grouped, {(20240201, 20240229): ["600519.SH"]})
        self.assertEqual(mock_is_confirmed_empty.call_count, 2)
        mock_is_confirmed_empty.assert_any_call(
            "600519.SH",
            "month",
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        mock_is_confirmed_empty.assert_any_call(
            "600519.SH",
            "month",
            date(2024, 2, 1),
            date(2024, 2, 29),
        )

    def test_group_by_missing_ranges_preserves_cross_year_month_range(self):
        """测试非 year 周期跨年缺失区间不会被扩展成整年范围."""
        completeness_results = {
            "600519.SH": CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=1,
                coverage_ratio=0.0,
                missing_ranges=[(date(2023, 11, 1), date(2024, 2, 29))],
                check_method="long_period",
            )
        }

        with patch(
            "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
            return_value=False,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            grouped = kline_data_sync_service._group_by_missing_ranges(
                completeness_results,
                "month",
            )

        self.assertEqual(grouped, {(20231101, 20240229): ["600519.SH"]})


class TestBatchSyncKlineData(unittest.TestCase):
    """批量同步测试类."""

    def test_batch_sync_kline_data_skips_api_for_confirmed_empty_ranges(self):
        """测试批量同步会跳过已确认为空的缺失区间，不发起 API 查询."""
        completeness_results = {
            "600519.SH": CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=1,
                coverage_ratio=0.0,
                missing_ranges=[(date(2024, 1, 1), date(2024, 1, 31))],
                check_method="long_period",
            )
        }

        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=True,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline"
            ) as mock_query_kline,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            result = kline_data_sync_service.batch_sync_kline_data(
                symbols=["600519.SH"],
                interval="month",
                start_date="20240101",
                end_date="20240131",
                interval_value=10010,
                completeness_results=completeness_results,
            )

        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.synced_records, 0)
        self.assertEqual(result.failed_codes, [])
        mock_query_kline.assert_not_called()

    def test_batch_sync_kline_data_skips_known_sdk_type_error_without_caching_empty(self):
        """测试批量同步遇到已知 SDK TypeError 时跳过该批次，且不写入空查询缓存."""
        completeness_results = {
            "600519.SH": CompletenessResult(
                is_complete=False,
                missing_count=1,
                total_count=1,
                coverage_ratio=0.0,
                missing_ranges=[(date(2024, 1, 1), date(2024, 1, 31))],
                check_method="long_period",
            )
        }

        with (
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.is_confirmed_empty",
                return_value=False,
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.amazing_data_client.query_kline",
                side_effect=TypeError("'NoneType' object cannot be interpreted as an integer"),
            ),
            patch(
                "galaxy_db_sync.database.services.kline_data_sync.empty_query_service.record_empty_result"
            ) as mock_record_empty,
        ):
            from galaxy_db_sync.database.services.kline_data_sync import (
                kline_data_sync_service,
            )

            result = kline_data_sync_service.batch_sync_kline_data(
                symbols=["600519.SH"],
                interval="month",
                start_date="20240101",
                end_date="20240131",
                interval_value=10010,
                completeness_results=completeness_results,
            )

        self.assertEqual(result.success_count, 0)
        self.assertEqual(result.synced_records, 0)
        self.assertEqual(result.failed_codes, [])
        mock_record_empty.assert_not_called()


if __name__ == "__main__":
    unittest.main()
