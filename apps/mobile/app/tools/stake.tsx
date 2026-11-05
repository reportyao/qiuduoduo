import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { useRouter } from "expo-router";
import { View } from "react-native";
import { Chip, Field, Text } from "@/components/ui";
import { kellyMath } from "@/features/tools/calc";
import { FormulaNote, ResultPanel, ResultRow, ToolScreen } from "@/features/tools/ToolLayout";
import { money, pct } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

const FRACTIONS = [
  { label: "全凯利", value: 1 },
  { label: "半凯利", value: 0.5 },
  { label: "四分一", value: 0.25 },
];

export default function StakeToolScreen() {
  const router = useRouter();
  const [bankroll, setBankroll] = useState("1000");
  const [probability, setProbability] = useState("54");
  const [decimal, setDecimal] = useState("2.05");
  const [fraction, setFraction] = useState(0.5);
  const total = Number(bankroll);
  const p = Number(probability) / 100;
  const odds = Number(decimal);
  const valid =
    Number.isFinite(total) && total > 0 &&
    Number.isFinite(p) && p > 0 && p < 1 &&
    Number.isFinite(odds) && odds > 1;
  const result = valid
    ? kellyMath({ bankroll: total, probability: p, decimal: odds, fraction, cap: 0.05 })
    : null;

  return (
    <ToolScreen
      headline="先有正期望，再谈仓位"
      title="仓位计算"
      eyebrow="纪律 · 单注上限"
      description="先有正期望，再谈仓位。输入你的本金、估计胜率和赔率，凯利公式会给出数学上限；本工具强制最多 5% 本金。"
      onBack={() => goBackOr(router)}
    >
      <Field label="本金" value={bankroll} onChangeText={setBankroll} keyboardType="number-pad" hint="单位：元" />
      <Field label="你估计的胜率" value={probability} onChangeText={setProbability} keyboardType="decimal-pad" hint="单位：%，例如 54" />
      <Field label="赔率（欧洲盘）" value={decimal} onChangeText={setDecimal} keyboardType="decimal-pad" />

      <Text variant="captionStrong" color={colors.muted} style={{ marginTop: spacing.base }}>凯利分数</Text>
      <View style={{ flexDirection: "row", gap: spacing.xs }}>
        {FRACTIONS.map((item) => (
          <Chip
            key={item.label}
            label={item.label}
            selected={fraction === item.value}
            onPress={() => setFraction(item.value)}
          />
        ))}
      </View>

      {!valid ? (
        <Text variant="small" color={colors.danger} style={{ marginTop: spacing.base }}>
          本金需大于 0，胜率在 0–100% 之间，赔率大于 1。
        </Text>
      ) : result ? (
        <>
          <ResultPanel title="数学仓位">
            <ResultRow label="单注期望收益率" value={pct(result.edge, 2)} strong tone={result.edge >= 0 ? "green" : "danger"} />
            <ResultRow label="全凯利比例" value={pct(result.fullKelly, 2)} />
            <ResultRow label={`${FRACTIONS.find((f) => f.value === fraction)?.label}建议`} value={money(result.stake, 0)} strong tone="green" />
            {result.capped ? <ResultRow label="已触及 5% 本金上限" value="是" tone="amber" /> : null}
          </ResultPanel>
          <FormulaNote>
            凯利 f* = (b·p − q) / b，其中 b = 赔率 − 1，p = 你估计的胜率，q = 1 − p。
            胜率估计一旦偏高，凯利会放大亏损；所以默认半凯利并加 5% 上限。
          </FormulaNote>
          {result.edge <= 0 ? (
            <Text variant="small" color={colors.danger} style={{ marginTop: spacing.base }}>
              当前赔率下期望为负。数学上没有仓位，不下注才是正确仓位。
            </Text>
          ) : null}
        </>
      ) : null}
    </ToolScreen>
  );
}
