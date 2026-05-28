"""批量同步 K 线数据 - 优化版本.

利用 AmazingData API 的批量查询能力，大幅提升同步效率。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from galaxy_db_sync.amazing_data.api.client import amazing_data_client
from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineDay
from galaxy_db_sync.database.services.trading_calendar import trading_calendar_service
from galaxy_db_sync.shared_kernel.utils import infer_security_type

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_extra_etf_codes(start_date: str, end_date: str) -> List[str]:
    """获取 EXTRA_ETF 的证券代码列表 - 使用 akshare."""
    logger.info(f"获取 EXTRA_ETF 代码列表...")

    try:
        import akshare as ak

        # 获取所有 ETF 基金列表
        df = ak.fund_etf_category_sina()

        # 构建代码列表 (格式: code.exchange)
        codes = []
        for _, row in df.iterrows():
            code = str(row['代码'])
            # 去掉可能的前缀
            code = code.replace('sz', '').replace('sh', '').replace('SZ', '').replace('SH', '')

            # 根据代码前缀判断交易所
            if code.startswith('15') or code.startswith('16'):
                codes.append(f"{code}.SZ")
            elif code.startswith('51') or code.startswith('56') or code.startswith('58') or code.startswith('59'):
                codes.append(f"{code}.SH")
            else:
                # 其他情况根据名称判断
                name = str(row.get('名称', ''))
                if 'SH' in name or '上海' in name:
                    codes.append(f"{code}.SH")
                else:
                    codes.append(f"{code}.SZ")

        logger.info(f"从 akshare 获取到 {len(codes)} 个 ETF 代码")
        return codes

    except Exception as e:
        logger.error(f"获取 ETF 代码列表失败: {e}")
        # 如果失败，返回之前 CLI 命令获取的代码数量
        logger.info("使用之前 CLI 命令获取的代码列表")
        return []


def batch_sync_kline_data(
    symbols: List[str],
    interval: str,
    start_date: date,
    end_date: date,
    interval_value: int,
    batch_size: int = 500,
) -> Tuple[int, int, List[str]]:
    """批量同步 K 线数据.

    Args:
        symbols: 证券代码列表
        interval: K线周期
        start_date: 开始日期
        end_date: 结束日期
        interval_value: SDK interval 值
        batch_size: 每批处理的证券数量

    Returns:
        (成功保存的总记录数, 成功处理的证券数, 失败的证券列表)
    """
    total_saved = 0
    success_count = 0
    failed_symbols = []

    # 分批处理
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        logger.info(f"处理批次 {i//batch_size + 1}/{(len(symbols) + batch_size - 1)//batch_size}: {len(batch)} 个证券")

        try:
            # 批量 API 查询
            start_int = int(start_date.strftime('%Y%m%d'))
            end_int = int(end_date.strftime('%Y%m%d'))

            logger.info(f"批量查询 {len(batch)} 个证券的 K 线数据...")
            kline_dict = amazing_data_client.query_kline(
                code_list=batch,
                begin_date=start_int,
                end_date=end_int,
                interval=interval_value,
            )

            # 批量保存
            saved_count = batch_save_kline_data(kline_dict, interval)
            total_saved += saved_count

            # 统计成功/失败
            for symbol in batch:
                if symbol in kline_dict and kline_dict[symbol] is not None and not kline_dict[symbol].empty:
                    success_count += 1
                else:
                    failed_symbols.append(symbol)

            logger.info(f"批次完成: 保存 {saved_count} 条记录")

        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            failed_symbols.extend(batch)

    return total_saved, success_count, failed_symbols


def batch_save_kline_data(kline_dict: Dict[str, pd.DataFrame], interval: str) -> int:
    """批量保存 K 线数据到数据库.

    Args:
        kline_dict: {symbol: DataFrame} 格式的 K 线数据
        interval: K线周期

    Returns:
        保存的记录总数
    """
    total_saved = 0
    records = []

    for symbol, df in kline_dict.items():
        if df is None or df.empty:
            continue

        security_type = infer_security_type(symbol) or "stock"

        for idx, row in df.iterrows():
            try:
                # 处理日期格式 - idx 可能是 int (YYYYMMDD) 或 datetime
                if isinstance(idx, int):
                    # 将 YYYYMMDD int 转换为 datetime
                    trade_time = datetime.strptime(str(idx), '%Y%m%d')
                elif isinstance(idx, datetime):
                    trade_time = idx
                elif isinstance(idx, date):
                    trade_time = datetime.combine(idx, datetime.min.time())
                else:
                    # 尝试解析为日期
                    trade_time = pd.to_datetime(idx).to_pydatetime()

                # 从 DataFrame 创建 KlineDay 记录
                record = KlineDay(
                    symbol=symbol,
                    trade_time=trade_time,
                    open=float(row.get('open', 0)),
                    high=float(row.get('high', 0)),
                    low=float(row.get('low', 0)),
                    close=float(row.get('close', 0)),
                    volume=int(row.get('volume', 0)),
                    amount=float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None,
                    security_type=security_type,
                )
                records.append(record)
            except Exception as e:
                logger.warning(f"创建记录失败 {symbol}: {e}")
                continue

    if records:
        # 批量插入
        session = db_manager.get_session()
        try:
            # 使用 bulk_save_objects 提高效率
            session.bulk_save_objects(records)
            session.commit()
            total_saved = len(records)
            logger.info(f"批量保存 {total_saved} 条记录到数据库")
        except Exception as e:
            session.rollback()
            logger.error(f"批量保存失败: {e}")
            # 回退到逐条保存
            total_saved = save_individual_records(records)
        finally:
            session.close()

    return total_saved


def save_individual_records(records: List) -> int:
    """逐条保存记录（批量失败时的回退方案）."""
    saved = 0
    session = db_manager.get_session()
    try:
        for record in records:
            try:
                session.merge(record)  # 使用 merge 处理重复
                saved += 1
                if saved % 1000 == 0:
                    session.commit()
            except Exception as e:
                logger.warning(f"保存单条记录失败: {e}")
                session.rollback()
        session.commit()
    finally:
        session.close()
    return saved


def main():
    """主函数."""
    # 初始化
    db_manager.initialize()

    # 参数设置
    start_date = date(2024, 1, 1)
    end_date = date.today()
    interval = "day"
    interval_value = 10008  # SDK day interval value

    logger.info("=" * 60)
    logger.info("批量 K 线数据同步 (优化版)")
    logger.info("=" * 60)
    logger.info(f"时间范围: {start_date} ~ {end_date}")
    logger.info(f"周期: {interval}")

    # 获取代码列表
    symbols = get_extra_etf_codes(
        start_date.strftime('%Y%m%d'),
        end_date.strftime('%Y%m%d')
    )

    if not symbols:
        logger.error("未获取到任何证券代码")
        return 1

    # 批量同步
    total_saved, success_count, failed_symbols = batch_sync_kline_data(
        symbols=symbols,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        interval_value=interval_value,
        batch_size=500,  # 每批 500 个证券
    )

    # 输出结果
    logger.info("=" * 60)
    logger.info("同步完成!")
    logger.info("-" * 60)
    logger.info(f"总记录数: {total_saved:,}")
    logger.info(f"成功证券数: {success_count}/{len(symbols)}")
    logger.info(f"失败证券数: {len(failed_symbols)}")

    if failed_symbols:
        logger.info(f"失败证券列表 (前 10 个): {failed_symbols[:10]}")

    return 0


if __name__ == "__main__":
    exit(main())
