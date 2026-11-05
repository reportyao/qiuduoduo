import { useMemo, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Alert, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import {
  Button,
  Card,
  Chip,
  ProgressBar,
  Text,
  useToast,
} from "@/components/ui";
import { useComplianceStore, type ExclusionChoice } from "@/features/compliance/complianceStore";
import { useLegalQuery, useMeQuery } from "@/features/account/queries";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { colors, spacing } from "@/theme/tokens";

const QUESTIONS = [
  "是否曾下注超过自己能承受的金额？",
  "是否需要不断加大注额才有感觉？",
  "输钱后是否总想尽快赢回来？",
  "是否借钱、变卖东西或挪用钱款继续？",
  "是否觉得自己可能已经控制不住？",
  "博彩是否让你感到压力、焦虑或失眠？",
  "是否有人批评过你的博彩行为？",
  "博彩是否影响了家庭、工作或社交？",
  "是否因为博彩而感到内疚？",
];

const ANSWERS = [
  { label: "从不", score: 0 },
  { label: "有时", score: 1 },
  { label: "经常", score: 2 },
  { label: "几乎总是", score: 3 },
];

function riskLevel(score: number): { label: string; tone: string; advice: string } {
  if (score === 0) return { label: "目前无明显风险", tone: colors.green, advice: "继续保持只把分析当参考，不追损。" };
  if (score <= 2) return { label: "低风险", tone: colors.amber, advice: "留意自己是否在追损或加注。可以先停一晚。" };
  if (score <= 7) return { label: "中等风险", tone: colors.amber, advice: "建议开启自排除 7 天，并和信任的人聊聊。" };
  return { label: "较高风险", tone: colors.danger, advice: "建议立即自排除并联系专业帮助。这不是意志力问题。" };
}

export default function ComplianceScreen() {
  const router = useRouter();
  const toast = useToast();
  const exclude = useComplianceStore((s) => s.exclude);
  const markSynced = useComplianceStore((s) => s.markSynced);
  const setPgsi = useComplianceStore((s) => s.setPgsi);
  const lastScore = useComplianceStore((s) => s.lastPgsiScore);
  const me = useMeQuery();
  const legal = useLegalQuery(me.data?.region ?? "cn");
  const [answers, setAnswers] = useState<number[]>(Array(QUESTIONS.length).fill(-1));
  const [submitted, setSubmitted] = useState(false);
  const score = useMemo(
    () => answers.reduce((sum, value) => sum + (value >= 0 ? ANSWERS[value].score : 0), 0),
    [answers],
  );
  const answered = answers.every((value) => value >= 0);
  const level = riskLevel(score);

  const confirmExclusion = (choice: ExclusionChoice) => {
    const label = choice === "permanent" ? "永久" : `${choice} 天`;
    Alert.alert(
      `确认自排除${label}？`,
      "期间无法查看预测与记录，到期前不可撤销。这是保护功能，不是惩罚。",
      [
        { text: "取消", style: "cancel" },
        {
          text: `确认排除${label}`,
          style: "destructive",
          onPress: () => {
            void (async () => {
              const saved = await exclude(choice);
              if (!saved) {
                Alert.alert("未能保存自排除", "本机存储不可用，请重试。未生效前不会离开本页。");
                return;
              }
              // 服务端通知偏好同步暂停，尽量避免排除期间仍收到推送；
              // 失败不阻塞本机强制拦截（离线也必须能自我排除）。
              void callApi(
                api.client.PUT("/me/notify-settings", { body: { paused: true } }),
              ).catch(() => {});
              // 服务端同步：多设备/重装后仍拦截；本地已强制生效，网络失败留给
              // useComplianceSync 在下次前台/登录时补写，绝不因为同步失败回滚本机拦截。
              const sync = callApi(api.client.POST("/compliance/self-exclusion", {
                body: {
                  days: choice === "permanent" ? null : choice,
                  permanent: choice === "permanent",
                  reason: "user_self_exclusion",
                },
              }))
                .then(() => {
                  markSynced();
                  return true;
                })
                .catch(() => false);
              const synced = await Promise.race([
                sync,
                new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 2500)),
              ]);
              toast.show(
                synced
                  ? "自排除已生效并同步到账号"
                  : "本机已生效；服务器同步失败，联网后会自动重试",
                synced ? "warning" : "error",
              );
              router.replace("/paused");
            })();
          },
        },
      ],
    );
  };

  return (
    <SettingsPage title="合规中心" subtitle="永远免费，不用于营销" onBack={() => goBackOr(router)}>
      <Card tone="green">
        <Text variant="h3">先照顾你这个人</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          球多多不卖彩票、不代购，也不靠你多下注赚钱。这里的功能永远免费，也不会出现在任何营销里。
        </Text>
      </Card>

      <Card style={styles.block}>
        <Text variant="overline" color={colors.green}>求助热线</Text>
        <Text variant="h3">{legal.data?.helpline || "当地心理援助热线"}</Text>
        <Text variant="caption" color={colors.muted}>
          {legal.data?.compliance || "如果你感到失控，请先联系专业帮助。数据分析不构成投注建议。"}
        </Text>
      </Card>

      <Card style={styles.block}>
        <Text variant="h3">自排除</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          生效后本机立即拦截首页、记录和记注，到期前不可撤销；联网后会同步到账号，换设备或重装仍受限制。
        </Text>
        <View style={styles.choiceRow}>
          <Button label="7 天" variant="secondary" onPress={() => confirmExclusion(7)} style={styles.flex} />
          <Button label="30 天" variant="secondary" onPress={() => confirmExclusion(30)} style={styles.flex} />
          <Button label="永久" variant="danger" onPress={() => confirmExclusion("permanent")} style={styles.flex} />
        </View>
      </Card>

      <Card style={styles.block}>
        <Text variant="h3">9 题自评</Text>
        <Text variant="small" color={colors.muted} style={styles.paragraph}>
          简化版 PGSI 自评，只在本机计算，不上传、不用于营销。它不能替代诊断。
        </Text>
        {QUESTIONS.map((question, index) => (
          <View key={question} style={styles.question}>
            <Text variant="small" style={styles.questionText}>{index + 1}. {question}</Text>
            <View style={styles.answerRow}>
              {ANSWERS.map((answer, answerIndex) => (
                <Chip
                  key={answer.label}
                  label={answer.label}
                  selected={answers[index] === answerIndex}
                  style={{ minHeight: 40 }}
                  onPress={() =>
                    setAnswers((prev) => prev.map((value, i) => (i === index ? answerIndex : value)))
                  }
                />
              ))}
            </View>
          </View>
        ))}
        <Button
          label={submitted ? "重新计算" : "看自评结果"}
          onPress={() => {
            if (!answered) {
              toast.show("9 题都回答后才能计算", "warning");
              return;
            }
            setSubmitted(true);
            setPgsi(score);
            void callApi(api.client.POST("/compliance/self-assessment", {
              body: { score, answers: Object.fromEntries(answers.map((value, index) => [String(index + 1), value])) },
            })).catch(() => {});
          }}
          variant="secondary"
          fullWidth
        />
        {submitted ? (
          <View style={styles.result}>
            <View style={styles.resultHead}>
              <Text variant="h3" color={level.tone}>{level.label}</Text>
              <Text variant="caption" color={colors.muted}>{score} / 27</Text>
            </View>
            <ProgressBar value={score / 27} tone={score >= 8 ? "danger" : score >= 3 ? "amber" : "green"} />
            <Text variant="small" color={colors.muted} style={styles.paragraph}>{level.advice}</Text>
          </View>
        ) : lastScore != null ? (
          <Text variant="caption" color={colors.subtle}>上次自评：{lastScore} / 27（仅本机可见）</Text>
        ) : null}
      </Card>

      <Text variant="caption" color={colors.subtle} center style={styles.footer}>
        自排除期间不会向你推送任何赛事内容。到期后也不会自动恢复营销，只会恢复基础功能。
      </Text>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  paragraph: { lineHeight: 20 },
  block: { gap: spacing.sm },
  choiceRow: { flexDirection: "row", gap: spacing.sm },
  flex: { flex: 1 },
  question: { gap: spacing.xs, paddingVertical: spacing.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line },
  questionText: { lineHeight: 19 },
  answerRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  result: { gap: spacing.xs, marginTop: spacing.sm },
  resultHead: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  footer: { lineHeight: 18, paddingHorizontal: spacing.base },
});
