#!/usr/bin/env python3
"""同步完整性验证脚本.

验证季/月/周线同步是否完成。

关键改进：
- 基于真实 ETF 上市日期计算预期值（而非假设所有 ETF 都有 2013-2024 数据）
- 通过抽样分析 API 返回的 ETF 数据可用性

Usage:
    PYTHONPATH=src python scripts/verify_sync_completeness.py
"""

import sys
from datetime import date
from random import sample

from sqlalchemy import func, distinct, text

from galaxy_db_sync.database.core.connection import DatabaseManager
from galaxy_db_sync.database.models.kline import KlineSeason, KlineMonth, KlineWeek, KlineYear
from galaxy_db_sync.shared_kernel.enums.interval import Interval
from galaxy_db_sync.amazing_data.api.client import amazing_data_client


def analyze_etf_data_availability(sample_size: int = 500) -> dict:
    """分析 ETF 数据可用性和上市日期分布.

    通过抽样查询 API 确定每只 ETF 的实际数据起始日期。

    Args:
        sample_size: 抽样数量

    Returns:
        dict: 包含分析结果
    """
    client = amazing_data_client.get_instance()

    # 获取 ETF 列表
    ad_codes = client.get_hist_code_list(
        security_type='EXTRA_ETF',
        start_date=20130101,
        end_date=20241231,
        local_path='./cache/'
    )

    total_etfs = len(ad_codes)
    sample_codes = sample(list(ad_codes), min(sample_size, total_etfs))

    # 获取日线数据以确定上市日期
    interval_value = Interval.DAY.to_sdk_period_value()

    has_data = 0
    no_data = 0
    listing_years = []

    for i, code in enumerate(sample_codes):
        if i % 100 == 0:
            print(f'  分析 ETF 数据可用性: {i}/{len(sample_codes)}...')

        try:
            result = client.query_kline(
                code_list=[code],
                begin_date=20100101,
                end_date=20241231,
                interval=interval_value,
            )
            if code in result and result[code] is not None and len(result[code]) > 0:
                df = result[code]
                first_date = df['kline_time'].min()
                listing_year = first_date.year
                listing_years.append(listing_year)
                has_data += 1
            else:
                no_data += 1
        except Exception:
            no_data += 1

    # 计算统计数据
    data_availability_rate = has_data / len(sample_codes) if sample_codes else 0
    estimated_etfs_with_data = int(total_etfs * data_availability_rate)

    # 计算平均上市年数
    current_year = 2024
    avg_years = sum(current_year - y + 1 for y in listing_years) / len(listing_years) if listing_years else 0

    # 计算预期记录数
    # 季线：每年 4 个季度
    # 月线：每年 12 个月
    # 周线：每年约 52 周
    expected_season = int(estimated_etfs_with_data * avg_years * 4)
    expected_month = int(estimated_etfs_with_data * avg_years * 12)
    expected_week = int(estimated_etfs_with_data * avg_years * 52)

    return {
        'total_etfs': total_etfs,
        'sample_size': len(sample_codes),
        'etfs_with_data': has_data,
        'etfs_without_data': no_data,
        'data_availability_rate': data_availability_rate,
        'estimated_etfs_with_data': estimated_etfs_with_data,
        'avg_years': avg_years,
        'listing_years': listing_years,
        'expected_counts': {
            'season': expected_season,
            'month': expected_month,
            'week': expected_week,
        },
    }


def verify_sync_completeness(skip_api_analysis: bool = False) -> bool:
    """验证同步完整性.

    Args:
        skip_api_analysis: 跳过 API 分析（使用硬编码预期值）

    Returns:
        bool: 所有检查是否通过
    """
    db = DatabaseManager()
    db.initialize()

    tables = {
        'season': KlineSeason,
        'month': KlineMonth,
        'week': KlineWeek,
    }
    interval_names = {
        'season': '季线',
        'month': '月线',
        'week': '周线',
    }

    all_passed = True

    with db.session() as session:
        print('=' * 70)
        print('季/月/周线同步完整性验证报告')
        print('=' * 70)

        # 1. 分析 ETF 数据可用性（计算真实预期值）
        if skip_api_analysis:
            print('\n【1. 预期值计算】（跳过 API 分析，使用保守估计）')
            # 基于之前的分析结果：约 44% ETF 有数据，平均 4.4 年
            total_etfs = 2496
            data_availability_rate = 0.44
            estimated_etfs_with_data = int(total_etfs * data_availability_rate)
            avg_years = 4.4

            expected_counts = {
                'season': int(estimated_etfs_with_data * avg_years * 4),
                'month': int(estimated_etfs_with_data * avg_years * 12),
                'week': int(estimated_etfs_with_data * avg_years * 52),
            }

            print(f'  ETF 总数: {total_etfs}')
            print(f'  数据可用率（保守估计）: {data_availability_rate * 100:.0f}%')
            print(f'  有数据 ETF 估计: {estimated_etfs_with_data}')
            print(f'  平均上市年数: {avg_years:.1f}')
        else:
            print('\n【1. 预期值计算】（基于 ETF 实际上市日期分析）')
            analysis = analyze_etf_data_availability(sample_size=300)

            total_etfs = analysis['total_etfs']
            data_availability_rate = analysis['data_availability_rate']
            estimated_etfs_with_data = analysis['estimated_etfs_with_data']
            avg_years = analysis['avg_years']
            expected_counts = analysis['expected_counts']

            print(f'  ETF 总数: {total_etfs}')
            print(f'  抽样数量: {analysis["sample_size"]}')
            print(f'  数据可用率: {data_availability_rate * 100:.1f}%')
            print(f'  有数据 ETF 估计: {estimated_etfs_with_data}')
            print(f'  平均上市年数: {avg_years:.1f}')

        # 2. 记录数验证
        print('\n【2. 记录数验证】')
        print(f'{"周期":<8} {"实际记录":>12} {"真实预期":>12} {"覆盖率":>10} {"状态":>8}')
        print('-' * 55)

        counts = {}
        for interval, model in tables.items():
            count = session.query(func.count(model.symbol)).scalar()
            counts[interval] = count
            exp = expected_counts[interval]
            ratio = count / exp * 100 if exp > 0 else 0
            # 覆盖率 >= 90% 视为通过（允许一定误差）
            status = '✓ 通过' if ratio >= 90 else '✗ 未达预期'
            if ratio < 90:
                all_passed = False
            name = interval_names[interval]
            print(f'{name:<8} {count:>12,} {exp:>12,} {ratio:>9.1f}% {status:>8}')

        # 3. ETF 覆盖率（有数据的 ETF 数量）
        print('\n【3. ETF 覆盖率】')
        print(f'预计有数据的 ETF: {estimated_etfs_with_data}')
        print(f'{"周期":<8} {"实际ETF数":>10} {"预期ETF数":>10} {"覆盖率":>10} {"状态":>8}')
        print('-' * 55)

        for interval, model in tables.items():
            covered = session.query(func.count(func.distinct(model.symbol))).scalar()
            ratio = covered / estimated_etfs_with_data * 100 if estimated_etfs_with_data > 0 else 0
            # 覆盖率 >= 90% 视为通过
            status = '✓ 通过' if ratio >= 90 else '✗ 未达预期'
            if ratio < 90:
                all_passed = False
            name = interval_names[interval]
            print(f'{name:<8} {covered:>10} {estimated_etfs_with_data:>10} {ratio:>9.1f}% {status:>8}')

        # 4. 时间范围
        print('\n【4. 时间范围】')
        print(f'{"周期":<8} {"起始日期":>12} {"结束日期":>12} {"状态":>8}')
        print('-' * 45)

        for interval, model in tables.items():
            result = session.query(func.min(model.trade_time), func.max(model.trade_time)).first()
            if result[0] and result[1]:
                # trade_time 可能是 datetime，需要转换为 date 比较
                min_time = result[0].date() if hasattr(result[0], 'date') else result[0]
                max_time = result[1].date() if hasattr(result[1], 'date') else result[1]
                # 起始日期应在 2013 年初附近，结束日期应接近当前
                start_ok = min_time <= date(2013, 1, 31)
                end_ok = max_time >= date(2024, 12, 1)
                status = '✓ 通过' if start_ok and end_ok else '✗ 异常'
            else:
                status = '✗ 无数据'
            name = interval_names[interval]
            print(f'{name:<8} {str(result[0]):>12} {str(result[1]):>12} {status:>8}')

        # 5. 数据质量检查
        print('\n【5. 数据质量检查】')

        # 重复检查
        for interval, model in tables.items():
            # 使用 text() 包装 SQL
            duplicate_check = session.execute(text(f"""
                SELECT COUNT(*) as dup_count
                FROM (
                    SELECT symbol, trade_time
                    FROM {model.__tablename__}
                    GROUP BY symbol, trade_time
                    HAVING COUNT(*) > 1
                ) t
            """)).scalar()

            status = '✓ 无重复' if duplicate_check == 0 else f'✗ {duplicate_check} 条重复'
            name = interval_names[interval]
            print(f'  {name} 重复检查: {status}')
            if duplicate_check > 0:
                all_passed = False

        # 汇总
        print('\n' + '=' * 70)
        if all_passed:
            print('✓ 所有验证通过，同步完成')
        else:
            print('✗ 存在未达标项，需进一步检查')
        print('=' * 70)

        return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='验证季/月/周线同步完整性')
    parser.add_argument('--skip-api', action='store_true',
                        help='跳过 API 分析，使用保守预期值（更快但可能不够准确）')
    args = parser.parse_args()

    success = verify_sync_completeness(skip_api_analysis=args.skip_api)
    sys.exit(0 if success else 1)
