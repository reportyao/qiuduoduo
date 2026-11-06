"""种子/同步 CLI：
    python -m app.seed <collector_sp_data.db> [--date YYYY-MM-DD]

1) 导入采集器数据（契约校验 → 对齐 → 去重入库）
2) 构建比赛日判决并封存

“现在”取采集器最新快照时间 —— 保证可复现，与采集器节奏一致（cron 驱动时即实时）。
比赛日窗口：当日 00:00 起 ~ 次日 04:59（竞彩跨日凌晨场规则），且只保留未开赛场次。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from .db import SessionLocal, init_db
from .modules.align import Aligner
from .modules.intl_odds import sports_for_trade_date, sync_the_odds_api
from .modules.ingest import import_collector_db
from .modules.timeutil import trade_date_from_kickoff, trade_window
from .modules.verdict import build_verdicts, promote_seal

CN = timezone(timedelta(hours=8))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("collector_db", help="采集器 sp_data.db 路径")
    ap.add_argument("--date", default=None, help="比赛日 YYYY-MM-DD，默认取库内最新快照日期")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        # 修订日期回填（W6 深审查：trade_date 冗余列一次性补齐）
        from .modules.sealchain import backfill_revision_dates
        n_bf = backfill_revision_dates(db)
        if n_bf:
            print(f"[chain] 回填修订 trade_date {n_bf} 条")

        # 防御：采集器推送与 cron 读取可能并发，先拷贝快照再读，避免半截文件
        import os
        import shutil
        import tempfile
        tmp_db = os.path.join(tempfile.gettempdir(), "jq_seed_copy.db")
        shutil.copyfile(args.collector_db, tmp_db)
        res = import_collector_db(db, tmp_db)
        print(f"[ingest] matches={res.matches_upserted} "
              f"snapshots={res.snapshots_inserted}/{res.snapshots_seen} "
              f"unresolved_alias={res.alias_unresolved}")

        aligner = Aligner(db)
        now_utc = datetime.now(timezone.utc)
        now_actual = datetime.now(CN)
        # 销售日由墙钟决定（05:00 前仍算前一日）；--date 仅用于显式回填。
        trade_date = args.date or trade_date_from_kickoff(now_actual)
        start, end = trade_window(trade_date)
        if not args.date:
            start = max(start, now_actual.strftime("%Y-%m-%d %H:%M:%S"))
        now_cn_str = now_actual.strftime("%Y-%m-%d %H:%M:%S")

        # 国际盘同步：按当日联赛动态选 sport key，避免为无关联赛烧配额。
        sports = sports_for_trade_date(db, trade_date)
        n_intl, note = sync_the_odds_api(db, aligner, now_utc, sports=sports)
        print(f"[intl] sports={sports or '[]'} {note}")

        # 本季 xG 增量同步（源不可达 → 跳过说明；恢复后模闸自动生效）
        from .modules.understat_sync import sync_understat
        n_xg, xg_note = sync_understat(now_utc)
        print(f"[xg] {xg_note}")

        # 赛果兜底（Understat 被云 IP 拦截时，用 football-data 进球代理补模型输入）
        from .modules.results_sync import sync_results_xg
        n_proxy, proxy_note = sync_results_xg(now_utc)
        print(f"[results] {proxy_note}")

        vs = build_verdicts(db, trade_date, now_cn_str, window_start=start, window_end=end)
        # 结算 + 当日锚点（W4）
        from .modules.settle import settle_verdicts, sync_results_football_data
        n_res, res_note = sync_results_football_data(db, aligner)
        n_settled = settle_verdicts(db)
        from .modules.sealchain import build_anchor, latest_chain_status
        anchor = build_anchor(db, trade_date)
        chain = latest_chain_status(db)
        if not chain["ok"]:
            # 断链告警（gate：断链告警演练通过）—— 不中断管线，但必须大声
            print(f"[chain-alert] 断链！date={chain['date']} broken_at={chain['broken_at']} —— 立即排查")
        print(f"[settle] 赛果 {res_note} · 结算 {n_settled} 注 · 锚点 {trade_date}: {(anchor.root_hash if anchor else '—')[:16]} · 链 {'OK' if chain['ok'] else 'BROKEN'}")
        sealed = promote_seal(db, trade_date)
        n_fail = {"price": 0, "market": 0, "model": 0}
        n_pending = {"price": 0, "market": 0, "model": 0}
        n_promoted = 0
        for v in vs:
            if v.status == "promoted":
                n_promoted += 1
            for g, r in v.gates.items():
                res_ = r["result"]
                if res_ == "fail":
                    n_fail[g] += 1
                elif res_ == "pending_data":
                    n_pending[g] += 1
        print(f"[verdict] date={trade_date} verdicts={len(vs)} promoted={n_promoted} "
              f"fail(价/市/模)={n_fail['price']}/{n_fail['market']}/{n_fail['model']} "
              f"pending(市/模)={n_pending['market']}/{n_pending['model']} "
              f"threshold={vs[0].rake_threshold if vs else '-'} sealed={sealed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
