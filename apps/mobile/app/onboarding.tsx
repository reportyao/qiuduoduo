import { useState } from "react";
import { Image, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePrefsStore } from "@/features/preferences/prefsStore";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { Button, Card, Icon, Text } from "@/components/ui";
import { colors, layout, radii, spacing } from "@/theme/tokens";

type Step = "age" | "intro";

export default function OnboardingScreen() {
  const router = useRouter();
  const setAgeDecision = usePrefsStore((s) => s.setAgeDecision);
  const [step, setStep] = useState<Step>("age");

  const chooseAdult = () => {
    setAgeDecision("adult");
    void callApi(api.client.POST("/gate/verify", { body: { adult: true } })).catch(() => {});
    setStep("intro");
  };
  const chooseMinor = () => {
    setAgeDecision("minor");
    void callApi(api.client.POST("/gate/verify", { body: { adult: false } })).catch(() => {});
    router.replace("/minor");
  };
  const enter = () => router.replace("/(tabs)");
  const openLegal = (doc: string) =>
    router.push({ pathname: "/legal", params: { doc } });

  return (
    <SafeAreaView style={styles.screen} edges={["top", "bottom", "left", "right"]}>
      <View style={styles.brandRow}>
        <Text variant="h2">球多多</Text>
        <Text variant="caption" color={colors.muted}>AI 赛前预测</Text>
      </View>

      <View style={styles.hero}>
        <Image
          source={require("../assets/mascot/zhuanjia.png")}
          style={styles.avatar}
          resizeMode="cover"
        />
        <View style={styles.halo} />
      </View>

      {step === "age" ? (
        <View style={styles.body}>
          <Text variant="overline" color={colors.green}>开始之前</Text>
          <Text variant="display" style={styles.title}>先确认一件事</Text>
          <Text variant="body" color={colors.muted} style={styles.lead}>
            球多多提供赛前预测与数据分析，不卖彩票、不代购。未满 18 周岁不能购买彩票，也不能使用预测与记录功能。
          </Text>

          <Card style={styles.note}>
            <View style={styles.noteRow}>
              <Icon name="lock-closed-outline" size={17} color={colors.green} />
              <Text variant="small" color={colors.muted} style={styles.noteText}>
                不收集出生日期，只在本机记录「已确认」状态。你随时可以在「我的 → 合规中心」查看。
              </Text>
            </View>
          </Card>

          <View style={styles.actions}>
            <Button label="我已年满 18 周岁，继续" onPress={chooseAdult} fullWidth />
            <Button label="未满 18 · 只看公开账本" onPress={chooseMinor} variant="secondary" fullWidth />
          </View>
          <Text variant="caption" color={colors.subtle} center style={styles.legal}>
            继续即表示你已阅读
            <Text variant="caption" color={colors.green} onPress={() => openLegal("terms")}>《服务说明》</Text>
            和
            <Text variant="caption" color={colors.green} onPress={() => openLegal("privacy")}>《隐私政策》</Text>
          </Text>
        </View>
      ) : (
        <View style={styles.body}>
          <Text variant="overline" color={colors.green}>球多多怎么用</Text>
          <Text variant="display" style={styles.title}>先看预测，再做决定。</Text>
          <Text variant="body" color={colors.muted} style={styles.lead}>
            对能算清的场次给出方向、预测概率和成立条件；看不准的就不发。
          </Text>

          <View style={styles.promises}>
            <Promise icon="analytics-outline" title="先看概率" body="方向、预测概率、模型 vs 市场，全部摊开。" />
            <Promise icon="shield-checkmark-outline" title="赛前封存" body="预测先上哈希，赛后改一个字都对不上。" />
            <Promise icon="close-circle-outline" title="不出也是答案" body="没有把握就不发预测，诚实告诉你今天别硬上。" />
          </View>

          <View style={styles.actions}>
            <Button label="看今日预测" onPress={enter} fullWidth iconRight="arrow-forward" />
            <Pressable onPress={() => setStep("age")} accessibilityRole="button" style={styles.back}>
              <Text variant="caption" color={colors.muted}>返回上一步</Text>
            </Pressable>
          </View>
          <Text variant="caption" color={colors.subtle} center style={styles.legal}>
            预测有误差，不构成投注建议。
          </Text>
        </View>
      )}
    </SafeAreaView>
  );
}

function Promise({
  icon,
  title,
  body,
}: {
  icon: React.ComponentProps<typeof Icon>["name"];
  title: string;
  body: string;
}) {
  return (
    <View style={styles.promise}>
      <View style={styles.promiseIcon}>
        <Icon name={icon} size={18} color={colors.green} />
      </View>
      <View style={styles.promiseText}>
        <Text variant="bodyStrong">{title}</Text>
        <Text variant="caption" color={colors.muted}>{body}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, paddingHorizontal: layout.pagePadding },
  brandRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: spacing.sm,
    paddingTop: spacing.sm,
  },
  hero: { alignItems: "center", marginTop: spacing.x4, height: 118 },
  avatar: {
    width: 112,
    height: 112,
    borderRadius: 56,
    borderWidth: 3,
    borderColor: colors.white,
    zIndex: 2,
  },
  halo: {
    position: "absolute",
    bottom: -18,
    width: 180,
    height: 80,
    borderRadius: 90,
    backgroundColor: colors.greenSoft,
    opacity: 0.9,
  },
  body: { flex: 1, marginTop: spacing.x4 },
  title: { marginTop: spacing.xs, marginBottom: spacing.base },
  lead: { lineHeight: 23 },
  note: { marginTop: spacing.x4, borderRadius: radii.lg, backgroundColor: colors.surface },
  noteRow: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  noteText: { flex: 1, lineHeight: 18 },
  actions: { marginTop: spacing.x4, gap: spacing.md },
  legal: { marginTop: spacing.base, lineHeight: 18 },
  back: { alignSelf: "center", padding: spacing.sm },
  promises: { marginTop: spacing.x4, gap: spacing.base },
  promise: { flexDirection: "row", gap: spacing.base, alignItems: "flex-start" },
  promiseIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  promiseText: { flex: 1, gap: 1 },
});
