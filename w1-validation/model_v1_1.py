#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DC 模型 v1.1 = v1（xG强度+主场+DCρ）+ 市场收缩纪律（>8pp 砍半）
输入: dc_model_v1_backtest.csv（v1 输出）
输出: 收缩后概率 + 与市场对照的最终 log loss
用法: python model_v1_1.py  （每次 v1 重跑后执行）
"""
import pandas as pd, numpy as np

bt = pd.read_csv("dc_model_v1_backtest.csv")
if "maxdev" not in bt.columns:
    bt["kbsum"] = 1/bt.bH + 1/bt.bD + 1/bt.bA
    bt["kbH"], bt["kbD"], bt["kbA"] = (1/bt.bH)/bt["kbsum"], (1/bt.bD)/bt["kbsum"], (1/bt.bA)/bt["kbsum"]
    bt["maxdev"] = np.maximum(np.abs(bt.mH-bt.kbH), np.abs(bt.mA-bt.kbA))

SHRINK_AT = 0.08   # 偏差阈值（TechSpec "市场收缩"纪律）
FACTOR = 0.5       # 砍半系数（v1.1 固定；v1.2 起改为按历史分位数自适应）

mask = bt.maxdev > SHRINK_AT
b2 = bt.copy()
for mc, kc in [("mH","kbH"),("mD","kbD"),("mA","kbA")]:
    b2.loc[mask, mc] = b2.loc[mask, mc]*FACTOR + b2.loc[mask, kc]*(1-FACTOR)
b2[["mH","mD","mA"]] = b2[["mH","mD","mA"]].div(b2[["mH","mD","mA"]].sum(1), axis=0)

def ll(df, cs):
    y = np.zeros((len(df),3)); y[df.ftr.values=="H",0]=1; y[df.ftr.values=="D",1]=1; y[df.ftr.values=="A",2]=1
    return -np.mean(np.log(np.clip((df[cs].values*y).sum(1), 1e-12, 1)))

print(f"v1.1 收缩纪律（>{SHRINK_AT:.0%} 场次砍半偏差）")
print(f"触发场次: {mask.sum()}/{len(bt)} ({mask.mean()*100:.1f}%)")
print(f"v1.0 log loss: {ll(bt,['mH','mD','mA']):.4f}")
print(f"v1.1 log loss: {ll(b2,['mH','mD','mA']):.4f}")
print(f"市场基准      : 0.9092")
b2.to_csv("dc_model_v1_1_output.csv", index=False)
print("输出: dc_model_v1_1_output.csv")
