from galaxy_db_sync.database.core.connection import db_manager
from galaxy_db_sync.database.models.kline import KlineMonth, KlineYear
from galaxy_db_sync.shared_kernel.utils import infer_security_type

db_manager.initialize()

print('月线表中被标记为SH_A的证券代码:')
with db_manager.session() as session:
    sh_a_month = session.query(KlineMonth.symbol).filter(KlineMonth.security_type == 'SH_A').distinct().all()
    print(f'总数: {len(sh_a_month)}')
    for code_tuple in sh_a_month[:20]:  # 只显示前20个
        code = code_tuple[0]
        inferred_type = infer_security_type(code)
        if inferred_type != 'SH_A':
            print(f'{code} -> 推断类型: {inferred_type}')
        else:
            print(f'{code} -> 推断类型: {inferred_type}')
    if len(sh_a_month) > 20:
        print(f'... 还有 {len(sh_a_month) - 20} 个')

print()
print('年线表中被标记为SH_A的证券代码:')
with db_manager.session() as session:
    sh_a_year = session.query(KlineYear.symbol).filter(KlineYear.security_type == 'SH_A').distinct().all()
    print(f'总数: {len(sh_a_year)}')
    for code_tuple in sh_a_year[:20]:  # 只显示前20个
        code = code_tuple[0]
        inferred_type = infer_security_type(code)
        if inferred_type != 'SH_A':
            print(f'{code} -> 推断类型: {inferred_type}')
        else:
            print(f'{code} -> 推断类型: {inferred_type}')
    if len(sh_a_year) > 20:
        print(f'... 还有 {len(sh_a_year) - 20} 个')
