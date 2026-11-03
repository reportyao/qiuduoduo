import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { useRouter } from "expo-router";
import { Field, Text } from "@/components/ui";
import { breakEvenMath } from "@/features/tools/calc";
import { FormulaNote, ResultPanel, ResultRow, ToolScreen } from "@/features/tools/ToolLayout";
import { money, pct } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

export default function BreakEvenToolScreen() {
  const router = useRouter();
  const [decimal, setDecimal] = useState("1.95");
  const [stake, setStake] = useState("100");
  const odds = Number(decimal);
  const amount = Number(stake);
  const valid = Number.isFinite(odds) && odds > 1 && Number.isFinite(amount) && amount > 0;
  const result = valid ? breakEvenMath(odds, amount) : null;

  return (
    <ToolScreen
      title="回本线"
      eyebrow="成本 · 胜负门槛"
      description="这个赔率要赢多少次才不亏？把回本线和你的真实判断放在一起看，别只看单场输赢。"
      onBack={() => goBackOr(router)}
    >
      <Field label="赔率（欧洲盘）" value={decimal} onChangeText={setDecimal} keyboardType="decimal-pad" />
      <Field label="单注金额" value={stake} onChangeText={setStake} keyboardType="number-pad" hint="单位：元" />
      {!valid ? (
        <Text variant="small" color={colors.danger} style={{ marginTop: spacing.base }}>
          赔率需大于 1，金额需大于 0。
        </Text>
      ) : result ? (
        <>
          <ResultPanel title="不亏需要赢">
            <ResultRow label="回本胜率" value={pct(result.winRate, 2)} strong tone="green" />
            <ResultRow label="每 10 注约需赢" value={`${result.winsOfTen.toFixed(1)} 注`} />
            <ResultRow label="押中一次盈利" value={money(result.profit, 2)} />
            <ResultRow label="未中一次亏损" value={money(result.loss, 2)} tone="danger" />
          </ResultPanel>
          <ResultPanel title="按市场概率的单注期望">
            <ResultRow label="期望值" value={money(result.expectedValue, 2)} strong tone={result.expectedValue >= 0 ? "green" : "danger"} />
            <ResultRow label="期望收益率" value={pct(result.expectedValue / amount, 2)} />
          </ResultPanel>
          <FormulaNote>
            回本胜率 = 1 / 欧洲盘赔率。比如 1.95 需要 51.28% 的胜率才不亏；
            再扣除抽水，长期胜率门槛还会更高。
          </FormulaNote>
        </>
      ) : null}
    </ToolScreen>
  );
}
