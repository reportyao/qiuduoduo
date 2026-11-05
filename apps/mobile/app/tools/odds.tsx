import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { useRouter } from "expo-router";
import { Field, Text } from "@/components/ui";
import { oddsMath } from "@/features/tools/calc";
import { FormulaNote, ResultPanel, ResultRow, ToolScreen } from "@/features/tools/ToolLayout";
import { pct } from "@/lib/format";
import { colors, spacing } from "@/theme/tokens";

export default function OddsToolScreen() {
  const router = useRouter();
  const [decimal, setDecimal] = useState("2.05");
  const value = Number(decimal);
  const valid = Number.isFinite(value) && value > 1;
  const result = valid ? oddsMath(value) : null;

  return (
    <ToolScreen
      headline="同一个价格，四种写法"
      title="赔率换算"
      eyebrow="赔率"
      description="同一个价格，欧洲盘、香港盘、印尼盘、美式盘写法不同。换错格式，账就会算错。"
      onBack={() => goBackOr(router)}
    >
      <Field
        label="欧洲盘（decimal）"
        value={decimal}
        onChangeText={setDecimal}
        keyboardType="decimal-pad"
        hint="含本金，例如 2.05 表示下 100 元返还 205 元。"
      />
      {!valid ? (
        <Text variant="small" color={colors.danger} style={{ marginTop: spacing.base }}>
          赔率需要大于 1。
        </Text>
      ) : result ? (
        <>
          <ResultPanel title="四种写法">
            <ResultRow label="欧洲盘" value={result.decimal.toFixed(2)} strong />
            <ResultRow label="香港盘" value={result.hk.toFixed(2)} />
            <ResultRow label="印尼盘" value={result.indo.toFixed(2)} />
            <ResultRow label="美式盘" value={result.american > 0 ? `+${result.american.toFixed(0)}` : result.american.toFixed(0)} />
          </ResultPanel>
          <ResultPanel title="隐含概率">
            <ResultRow label="未去水" value={pct(result.implied, 2)} strong tone="amber" />
            <ResultRow label="公平概率（零抽水）" value="需结合三项赔率计算" />
          </ResultPanel>
          <FormulaNote>
            香港盘 = 欧洲盘 − 1；印尼盘 = 欧赔≥2 时取欧赔−1，否则取 −1/(欧赔−1)；
            美式盘 = 欧赔≥2 时取 +(欧赔−1)×100，否则取 −100/(欧赔−1)。
          </FormulaNote>
        </>
      ) : null}
    </ToolScreen>
  );
}
