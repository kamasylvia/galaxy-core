#!/usr/bin/env python3
"""
交易日历批量同步脚本

此脚本用于批量同步指定年份范围的交易日历数据到数据库中。
"""

import argparse
import logging
from datetime import datetime, date
import pandas as pd
import akshare as ak
from sqlalchemy import and_
from galaxy_db_bridge.database.core.connection import db_manager
from galaxy_db_bridge.database.models.trading_calendar import TradingCalendar
from galaxy_db_bridge.database.services.trading_calendar import trading_calendar_service


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )


def sync_years(start_year: int, end_year: int, market: str = "SSE"):
    """
    同步指定年份范围的交易日历

    Args:
        start_year: 开始年份
        end_year: 结束年份
        market: 市场类型，默认为 SSE
    """
    logger = logging.getLogger(__name__)

    logger.info(f"开始同步 {start_year}-{end_year} 年的 {market} 交易日历...")

    success_count = 0
    total_days = 0

    # 一次性获取所有年份的数据，以减少API调用
    try:
        logger.info(f"从 akshare 获取 {start_year} 到 {end_year} 年的交易日历...")

        # 使用 akshare 获取交易日历
        df = ak.tool_trade_date_hist_sina()

        # 转换日期格式
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        # 筛选指定日期范围
        start_date = date(start_year, 1, 1)
        end_date = date(end_year, 12, 31)
        filtered_df = df[
            (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
        ]

        trading_days = filtered_df["trade_date"].tolist()

        logger.info(f"从 akshare 获取到 {len(trading_days)} 个交易日")

        # 使用标准化的市场代码（SSE）
        market_display = "SSE"

        # 确定完整的日期范围
        start_date = date(start_year, 1, 1)
        end_date = date(end_year, 12, 31)

        # 清除指定年份范围的数据
        session = db_manager.get_session()
        try:
            # 删除指定年份范围内的数据
            session.query(TradingCalendar).filter(
                and_(
                    TradingCalendar.market == market_display,
                    TradingCalendar.year >= start_year,
                    TradingCalendar.year <= end_year,
                )
            ).delete(synchronize_session=False)

            session.commit()
            logger.info(f"已清除 {start_year}-{end_year} 年的数据")
        except Exception as e:
            session.rollback()
            logger.error(f"清除数据时出错: {e}")
            raise
        finally:
            session.close()

        # 保存数据到数据库，传入完整的日期范围以包含非交易日
        trading_calendar_service._save_to_db(
            trading_days, market_display, start_date, end_date
        )

        # 计算每年的天数
        yearly_counts = {}
        for trade_date in trading_days:
            year = trade_date.year
            if year >= start_year and year <= end_year:
                yearly_counts[year] = yearly_counts.get(year, 0) + 1

        success_count = len(yearly_counts)
        total_days = sum(yearly_counts.values())

        for year in range(start_year, end_year + 1):
            count = yearly_counts.get(year, 0)
            logger.info(f"{year} 年同步完成，共 {count} 个交易日")

    except Exception as e:
        logger.error(f"同步 {start_year}-{end_year} 年数据时出错: {e}")
        raise

    logger.info(
        f"同步完成！成功同步 {success_count} 年数据，总共 {total_days} 个交易日"
    )


def sync_multiple_markets(start_year: int, end_year: int, markets: list):
    """
    同步多个市场的交易日历

    Args:
        start_year: 开始年份
        end_year: 结束年份
        markets: 市场代码列表
    """
    logger = logging.getLogger(__name__)

    for market in markets:
        logger.info(f"开始同步 {market} 市场...")
        try:
            sync_years(start_year, end_year, market)
        except Exception as e:
            logger.error(f"同步 {market} 市场时出错: {e}")
            continue


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量同步交易日历数据")
    parser.add_argument(
        "--start-year", type=int, default=2010, help="开始年份 (默认: 2010)"
    )
    parser.add_argument(
        "--end-year", type=int, default=2026, help="结束年份 (默认: 2026)"
    )
    parser.add_argument(
        "--market", type=str, default="SSE", help="市场类型 (默认: SSE)"
    )
    parser.add_argument("--all-markets", action="store_true", help="同步所有支持的市场")

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    # 初始化数据库
    logger.info("初始化数据库连接...")
    db_manager.initialize()

    start_time = datetime.now()

    try:
        # 中国市场统一交易时间，只需要导入沪市数据即可
        logger.info(f"开始同步 {args.start_year} 到 {args.end_year} 年的交易日历数据")
        logger.info("中国市场统一交易时间，仅使用沪市作为代表")

        # 只同步沪市数据，因为中国市场统一交易时间
        sync_years(args.start_year, args.end_year, "SSE")

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info(f"同步任务完成，耗时: {duration}")

    except KeyboardInterrupt:
        logger.info("用户中断了同步任务")
    except Exception as e:
        logger.error(f"同步过程中发生错误: {e}")


if __name__ == "__main__":
    main()
