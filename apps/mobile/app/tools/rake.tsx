import { useMemo, useState } from "react";
import { useRouter } from "expo-router";
import { Field, Text } from "@/components/ui";
import { rakeMath } from "@/features/tools/calc";
import { FormulaNote, ResultPanel, ResultRow, ToolScreen } from "@/features/tools/ToolLayout";
import { pct } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

export default function RakeToolScreen() {
  const router = useRouter();
  const [home, setHome] = useState("2.20");
  const [draw, setDraw] = useState("4.40");
  const [away, setAway] = useState("2.19");

  const values = [Number(home), Number(draw), Number(away)];
  const valid = values.every((v) => Number.isFinite(v) && v > 1);
  const result = useMemo(
    () => (valid ? rakeMath([values[0], values[1], values[2]]) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [home, draw, away, valid],
  );

  return (
    <ToolScreen
      title="抽水计算"
      eyebrow="价闸 · 先算入场费"
      description="输入主胜/平/客胜三项欧赔，算出官方定价抽水、真实返还率和去水后的概率。抽水是开赛前就付掉的钱。"
      onBack={() => router.back()}
    >
      <Field label="主胜赔率" value={home} onChangeText={setHome} keyboardType="decimal-pad" />
      <Field label="平局赔率" value={draw} onChangeText={setDraw} keyboardType="decimal-pad" />
      <Field label="客胜赔率" value={away} onChangeText={setAway} keyboardType="decimal-pad" />

      {!valid ? (
        <Text variant="small" color={colors.danger} style={{ marginTop: spacing.base }}>
          三项赔率都需要大于 1。
        </Text>
      ) : result ? (
        <>
          <ResultPanel title="抽水与返还">
            <ResultRow label="官方抽水（overround 归一）" value={pct(result.rake, 2)} strong tone="danger" />
            <ResultRow label="理论返还率" value={pct(result.returnRate, 2)} strong tone="green" />
            <ResultRow label="超额投注比例" value={pct(result.overround, 2)} />
          </ResultPanel>
          <ResultPanel title="去水后的真实概率">
            <ResultRow label="主胜" value={pct(result.probs[0], 2)} />
            <ResultRow label="平局" value={pct(result.probs[1], 2)} />
            <ResultRow label="客胜" value={pct(result.probs[2], 2)} />
          </ResultPanel>
          <ResultPanel title="公平赔率（零抽水）">
            <ResultRow label="主胜" value={result.fairOdds[0].toFixed(3)} />
            <ResultRow label="平局" value={result.fairOdds[1].toFixed(3)} />
            <ResultRow label="客胜" value={result.fairOdds[2].toFixed(3)} />
          </ResultPanel>
          <FormulaNote>
            抽水 = (Σ1/赔率 − 1) / Σ1/赔率；返还率 = 1 / Σ1/赔率；去水概率 = (1/赔率) / Σ1/赔率。
          </FormulaNote>
        </>
      ) : null}
    </ToolScreen>
  );
}
