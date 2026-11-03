# -*- coding: utf-8 -*-
"""W1 三数验证：football-data.co.uk 20 年历史
验证①单场返还率分布 ②抽水离散度 ③多庄家vs共识偏差（官方SP代理）
"""
import pandas as pd, numpy as np, io, urllib.request, os, json, sys

LEAGUES = {"E0":"英超","D0":"德甲","I0":"意甲","SP1":"西甲","F1":"法甲"}
SEASONS = [f"{y}{str(y+1)[2:]}" for y in range(2005, 2025)]  # 05-06 → 24-25 共20季
OUT = "data"; os.makedirs(OUT, exist_ok=True)

def fetch(lg, season):
    path = f"{OUT}/{lg}_{season}.csv"
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return pd.read_csv(path, low_memory=False)
    url = f"https://www.football-data.co.uk/mmz4281/{season[2:]}/{lg}.csv"
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read()
        if len(raw) < 2000: return None
        open(path, "wb").write(raw)
        return pd.read_csv(io.BytesIO(raw), low_memory=False)
    except Exception:
        return None

frames = []
total_bytes = 0
for lg, name in LEAGUES.items():
    for season in SEASONS:
        df = fetch(lg, season)
        if df is None or len(df) == 0: continue
        df["Lg"], df["Season"] = name, season
        total_bytes += os.path.getsize(f"{OUT}/{lg}_{season}.csv")
        frames.append(df)

all_df = pd.concat(frames, ignore_index=True)
mb = total_bytes / 1024 / 1024
print(f"== 数据量 ==")
print(f"下载文件: {len(os.listdir(OUT))} 个 CSV · 原始体积 {mb:.1f} MB")
print(f"总场次: {len(all_df):,} · 覆盖赛季: {all_df['Season'].nunique()} 季 × 5 联赛")
print(f"时间跨度: {all_df['Season'].min()} → {all_df['Season'].max()}")

# ---- 有效赔率列（B365 全期存在；PS=平博即 Pinnacle）----
for c in ["B365H","B365D","B365A","PSH","PSD","PSA"]:
    all_df[c] = pd.to_numeric(all_df.get(c), errors="coerce")

d = all_df.dropna(subset=["B365H","B365D","B365A"]).copy()
d["valid"] = (d["B365H"]>1)&(d["B365D"]>1)&(d["B365A"]>1)
d = d[d.valid]
print(f"有完整赔率的场次: {len(d):,}")

# ---- 数① 单场返还率分布 ----
d["ret_b365"] = 1/(1/d["B365H"]+1/d["B365D"]+1/d["B365A"])
r = d["ret_b365"]
print(f"\n== 数① 单场返还率（1X2，B365）==")
print(f"均值 {r.mean()*100:.2f}% · 中位 {r.median()*100:.2f}% · P5 {r.quantile(.05)*100:.2f}% · P95 {r.quantile(.95)*100:.2f}% · 极差 {(r.max()-r.min())*100:.1f}pp")
print(f"≈ 即单场抽水中位数 {(1-r.median())*100:.2f}%")

# ---- 数② 抽水离散度（这是闸一的命门）----
m = (1 - r) * 100
print(f"\n== 数② 单场抽水离散度 ==")
print(f"均值 {m.mean():.2f}% · 标准差 {m.std():.2f}pp · P5 {m.quantile(.05):.2f}% · P95 {m.quantile(.95):.2f}%")
print(f"极差（最深-最浅）: {m.max():.2f}% - {m.min():.2f}% = {m.max()-m.min():.2f}pp")
for thr in [8, 10, 12]:
    print(f"  抽水>{thr}% 的场次占比: {(m>thr).mean()*100:.1f}%   抽水<{thr-2}% 占比: {(m<thr-2).mean()*100:.1f}%")
# 按赛季看离散是否稳定
by_season = d.groupby("Season")["ret_b365"].agg(["median","max","min"])
spread = (by_season["max"]-by_season["min"])*100
print(f"  逐赛季极差范围: {spread.min():.1f} ~ {spread.max():.1f}pp（>5pp 门限 {'全部通过' if spread.min()>5 else '存在不通过赛季'}）")

# ---- 数③ 单庄家 vs 共识偏差（官方SP代理）----
p = all_df.dropna(subset=["PSH","PSD","PSA"]).copy()
p = p[(p["PSH"]>1)&(p["PSD"]>1)&(p["PSA"]>1)]
p["ret_ps"] = 1/(1/p["PSH"]+1/p["PSD"]+1/p["PSA"])
p["fairH"], p["fairD"], p["fairA"] = (1/p["PSH"])/p["ret_ps"], (1/p["PSD"])/p["ret_ps"], (1/p["PSA"])/p["ret_ps"]
p["b365H"] = pd.to_numeric(p["B365H"], errors="coerce")
p = p.dropna(subset=["b365H"])
p["imp_b365H"] = (1/p["b365H"])/ (1/(1/p["B365H"]+1/p["B365D"]+1/p["B365A"]))
p["dev"] = (p["imp_b365H"] - p["fairH"]).abs() * 100
print(f"\n== 数③ 单庄家隐含 vs 平博公允 偏差（官方SP代理，{len(p):,} 场）==")
print(f"主胜方向偏差: 均值 {p['dev'].mean():.2f}pp · P95 {p['dev'].quantile(.95):.2f}pp · >3pp 占比 {(p['dev']>3).mean()*100:.1f}% · >5pp 占比 {(p['dev']>5).mean()*100:.1f}%")
print(f"（>3pp 占比高 = 不同庄家对同一场的定价分歧真实存在 → 官方 vs 国际盘的偏差同理可期）")

# ---- 三数验证判定 ----
g1 = 88 <= r.median()*100 <= 96
g2 = (m.max()-m.min()) > 5 and m.std() > 1.5
g3 = (p["dev"]>3).mean() > 0.30
print(f"\n== 三数验证判定 ==")
print(f"① 返还率集中 88–96%（成本故事成立）: {'✓ 通过' if g1 else '✗ 不通过'}")
print(f"② 抽水极差 >5pp（'挑水浅'成立）: {'✓ 通过' if g2 else '✗ 不通过'}")
print(f"③ 定价偏差 >3pp 占比 >30%（信息差存在）: {'✓ 通过' if g3 else '✗ 不通过'}")
print(f"\n总判定: {'✓✓✓ 三数全部通过 → 按 PRD 主线走' if (g1 and g2 and g3) else '⚠ 有不通过项 → 见 PRD §13 转向条件'}")
d[["Div","Season","Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR","B365H","B365D","B365A","ret_b365"]].to_csv("validation_data.csv", index=False)
print(f"\n明细已存: validation_data.csv ({len(d):,} 行)")
