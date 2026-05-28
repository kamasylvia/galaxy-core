#!/usr/bin/env python3
"""交易日历批量同步脚本。"""

import argparse
import logging
from datetime import date, datetime

import akshare as ak
import pandas as pd

from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.trading_calendar import TradingCalendar
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def sync_years(start_year: int, end_year: int):
    """同步指定年份范围的共享交易日历。"""
    logger = logging.getLogger(__name__)
    logger.info(f"开始同步 {start_year}-{end_year} 年的共享交易日历...")

    success_count = 0
    total_days = 0

    try:
        logger.info(f"从 akshare 获取 {start_year} 到 {end_year} 年的交易日历...")
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        start_date = date(start_year, 1, 1)
        end_date = date(end_year, 12, 31)
        filtered_df = df[
            (df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)
        ]
        trading_days = filtered_df["trade_date"].tolist()

        logger.info(f"从 akshare 获取到 {len(trading_days)} 个交易日")

        session = db_manager.get_session()
        try:
            session.query(TradingCalendar).filter(
                TradingCalendar.year >= start_year,
                TradingCalendar.year <= end_year,
            ).delete(synchronize_session=False)
            session.commit()
            logger.info(f"已清除 {start_year}-{end_year} 年的数据")
        except Exception as e:
            session.rollback()
            logger.error(f"清除数据时出错: {e}")
            raise
        finally:
            session.close()

        trading_calendar_service._save_to_db(trading_days, start_date, end_date)

        yearly_counts = {}
        for trade_date in trading_days:
            year = trade_date.year
            if start_year <= year <= end_year:
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量同步交易日历数据")
    parser.add_argument(
        "--start-year", type=int, default=2010, help="开始年份 (默认: 2010)"
    )
    parser.add_argument(
        "--end-year", type=int, default=2026, help="结束年份 (默认: 2026)"
    )
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("初始化数据库连接...")
    db_manager.initialize()

    start_time = datetime.now()

    try:
        logger.info(f"开始同步 {args.start_year} 到 {args.end_year} 年的交易日历数据")
        logger.info("中国市场统一交易时间，使用共享交易日历")
        sync_years(args.start_year, args.end_year)

        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"同步任务完成，耗时: {duration}")
    except KeyboardInterrupt:
        logger.info("用户中断了同步任务")
    except Exception as e:
        logger.error(f"同步过程中发生错误: {e}")


if __name__ == "__main__":
    main()
