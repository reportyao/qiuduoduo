import type { ReactNode } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, Text } from "@/components/ui";
import { colors, layout, spacing } from "@/theme/tokens";

export function ToolScreen({
  title,
  headline,
  eyebrow,
  description,
  onBack,
  children,
}: {
  title: string;
  headline?: string;
  eyebrow: string;
  description: string;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <AppScreen bottom={false}>
      <AppHeader title={title} showAssistant={false} onBack={onBack} />
      <ScrollView
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.content}
      >
        <Text variant="overline" color={colors.green}>{eyebrow}</Text>
        <Text variant="display" style={styles.title}>{headline ?? title}</Text>
        <Text variant="body" color={colors.muted} style={styles.lead}>{description}</Text>
        {children}
        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          本工具只做数学计算，不构成投注建议。所有公式在页面内公开，可自行复算。
        </Text>
      </ScrollView>
    </AppScreen>
  );
}

export function ResultPanel({
  title = "结果",
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <Card style={styles.result}>
      <Text variant="overline" color={colors.green}>{title}</Text>
      {children}
    </Card>
  );
}

export function ResultRow({
  label,
  value,
  strong = false,
  tone = "default",
}: {
  label: string;
  value: string;
  strong?: boolean;
  tone?: "default" | "green" | "danger" | "amber";
}) {
  const color = {
    default: colors.ink,
    green: colors.green,
    danger: colors.danger,
    amber: colors.amber,
  }[tone];
  return (
    <View style={styles.resultRow}>
      <Text variant="small" color={colors.muted}>{label}</Text>
      <Text variant={strong ? "h3" : "bodyStrong"} color={color} style={styles.resultValue} selectable>
        {value}
      </Text>
    </View>
  );
}

export function FormulaNote({ children }: { children: ReactNode }) {
  return (
    <View style={styles.formula}>
      <Text variant="caption" color={colors.muted} style={styles.formulaText}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.xl, paddingBottom: spacing.x7 },
  title: { marginTop: spacing.xs },
  lead: { marginTop: spacing.sm, lineHeight: 22 },
  footer: { marginTop: spacing.x4, lineHeight: 18 },
  result: { marginTop: spacing.x4, gap: spacing.xs },
  resultRow: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: spacing.base,
    paddingVertical: spacing.xs,
  },
  resultValue: { flexShrink: 1, textAlign: "right" },
  formula: {
    marginTop: spacing.base,
    backgroundColor: colors.bgElevated,
    borderRadius: 12,
    padding: spacing.base,
  },
  formulaText: { lineHeight: 18 },
});
