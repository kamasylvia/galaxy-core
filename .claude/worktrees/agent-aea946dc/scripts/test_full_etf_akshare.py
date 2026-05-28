#!/usr/bin/env python3
"""EXTRA_ETF 全量年线同步 - 使用 akshare 获取代码列表."""

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 设置日志
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f'full_sync_akshare_{timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)


def get_etf_codes_from_ad() -> list[str]:
    """使用 AmazingData SDK 获取 ETF 代码列表."""
    logger.info("使用 AmazingData SDK 获取 ETF 代码列表...")

    try:
        from galaxy_db_sync.amazing_data.api.client import amazing_data_client

        # 确保客户端已初始化
        client = amazing_data_client.get_instance()

        # 使用 YYYYMMDD 格式日期
        codes = client.get_hist_code_list(
            security_type='EXTRA_ETF',
            start_date=20210101,  # YYYYMMDD 格式
            end_date=20231231,
            local_path='./cache/'
        )

        logger.info(f"从 AmazingData 获取到 {len(codes)} 个 ETF 代码")
        return codes

    except Exception as e:
        logger.error(f"从 AmazingData 获取 ETF 代码失败: {e}")
        logger.info("回退到 akshare 获取...")
        return get_etf_codes_from_akshare()


def get_etf_codes_from_akshare() -> list[str]:
    """使用 akshare 获取 ETF 代码列表 (回退方案)."""
    logger.info("使用 akshare 获取 ETF 代码列表...")

    try:
        import akshare as ak

        # 获取所有 ETF 基金列表
        df = ak.fund_etf_category_sina()

        # 构建代码列表 (格式: code.exchange)
        codes = []
        invalid_codes = []
        for _, row in df.iterrows():
            raw_code = str(row['代码']).strip()
            name = str(row.get('名称', ''))

            # 处理格式: sz169201 或 sh510050 -> 169201.SZ
            code = raw_code.lower()

            if code.startswith('sz'):
                code_num = code[2:]
                if code_num.isdigit() and len(code_num) == 6:
                    codes.append(f"{code_num}.SZ")
                else:
                    invalid_codes.append(raw_code)
            elif code.startswith('sh'):
                code_num = code[2:]
                if code_num.isdigit() and len(code_num) == 6:
                    codes.append(f"{code_num}.SH")
                else:
                    invalid_codes.append(raw_code)
            elif code.isdigit() and len(code) == 6:
                # 纯数字，根据代码前缀判断交易所
                if code.startswith('15') or code.startswith('16'):
                    codes.append(f"{code}.SZ")
                elif code.startswith('51') or code.startswith('56') or code.startswith('58') or code.startswith('59'):
                    codes.append(f"{code}.SH")
                else:
                    # 默认根据名称判断
                    if 'SH' in name or '上海' in name:
                        codes.append(f"{code}.SH")
                    else:
                        codes.append(f"{code}.SZ")
            else:
                invalid_codes.append(raw_code)

        logger.info(f"从 akshare 获取到 {len(codes)} 个有效 ETF 代码")
        if invalid_codes:
            logger.warning(f"跳过 {len(invalid_codes)} 个无效代码: {invalid_codes[:10]}...")
        return codes

    except Exception as e:
        logger.error(f"从 akshare 获取 ETF 代码失败: {e}")
        return []


def get_etf_codes() -> list[str]:
    """获取 ETF 代码列表 (优先使用 AD SDK)."""
    return get_etf_codes_from_ad()


def run_sync_for_codes(codes: list[str], interval: str, start: str, end: str) -> dict:
    """执行指定代码列表的同步.

    由于 CLI 参数长度限制，我们分批执行。
    """
    logger.info("=" * 70)
    logger.info(f"开始同步 {len(codes)} 只 ETF")
    logger.info("=" * 70)

    total_start = time.perf_counter()
    total_api_calls = 0
    total_records = 0
    batch_num = 0

    # 分批处理，每批最多 100 只（避免命令行过长）
    batch_size = 100

    for i in range(0, len(codes), batch_size):
        batch_num += 1
        batch = codes[i:i + batch_size]
        batch_str = '[' + ','.join(batch) + ']'

        cmd = [
            'uv', 'run', 'python', '-m', 'galaxy_db_sync', 'kline',
            batch_str,
            '--interval', interval,
            '--start', start,
            '--end', end,
        ]

        logger.info(f"\n批次 {batch_num}/{(len(codes) + batch_size - 1) // batch_size}: {len(batch)} 只 ETF")
        logger.info(f"命令长度: {len(' '.join(cmd))} 字符")

        batch_start = time.perf_counter()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=Path(__file__).parent.parent
            )

            batch_duration = time.perf_counter() - batch_start

            # 解析输出
            stdout = result.stdout
            stderr = result.stderr

            # 统计 API 调用
            api_calls = stdout.count('Fetched kline for')
            total_api_calls += api_calls

            logger.info(f"批次 {batch_num} 完成:")
            logger.info(f"  耗时: {batch_duration:.2f}s")
            logger.info(f"  API调用: {api_calls}")
            logger.info(f"  返回码: {result.returncode}")

            if result.returncode != 0:
                logger.warning(f"  批次执行可能失败，stderr: {stderr[:500]}")

            # 等待一下避免 API 限流
            time.sleep(1)

        except Exception as e:
            logger.error(f"批次 {batch_num} 执行失败: {e}")

    total_duration = time.perf_counter() - total_start

    return {
        'total_codes': len(codes),
        'batches': batch_num,
        'total_duration': total_duration,
        'api_calls': total_api_calls,
    }


def main():
    """主函数."""
    logger.info("=" * 70)
    logger.info("EXTRA_ETF 全量年线同步 (使用 AmazingData SDK 获取代码)")
    logger.info("=" * 70)

    # 获取 ETF 代码 (优先使用 AD SDK)
    codes = get_etf_codes()

    if not codes:
        logger.error("未获取到任何 ETF 代码")
        return

    logger.info(f"准备同步 {len(codes)} 只 ETF 的 2021-2023 年线数据")

    # 执行同步
    result = run_sync_for_codes(
        codes=codes,
        interval='year',
        start='2021',
        end='2023'
    )

    # 生成报告
    logger.info("\n" + "=" * 70)
    logger.info("同步完成报告")
    logger.info("=" * 70)
    logger.info(f"总 ETF 数: {result['total_codes']}")
    logger.info(f"总批次数: {result['batches']}")
    logger.info(f"总耗时: {result['total_duration']:.2f}s ({result['total_duration']/60:.2f}分钟)")
    logger.info(f"API 调用次数: {result['api_calls']}")
    logger.info(f"平均每批耗时: {result['total_duration']/result['batches']:.2f}s")
    logger.info(f"平均每只耗时: {result['total_duration']/result['total_codes']:.2f}s")
    logger.info(f"吞吐量: {result['total_codes']/result['total_duration']:.2f} 只/秒")
    logger.info("=" * 70)

    # 保存结果
    import json
    stats_file = log_dir / f'full_sync_akshare_{timestamp}.json'
    with open(stats_file, 'w') as f:
        json.dump(result, f, indent=2)
    logger.info(f"统计信息已保存到: {stats_file}")


if __name__ == "__main__":
    main()
