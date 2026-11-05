import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Share, ScrollView, StyleSheet, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, ErrorState, Skeleton, Text, useToast } from "@/components/ui";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useAuthStore } from "@/features/auth/authStore";
import { useBetsQuery } from "@/features/records/queries";
import { useMeQuery } from "@/features/account/queries";
import { useWatchQuery } from "@/features/inbox/queries";
import { useShareVerdictMutation } from "@/features/assistant/queries";
import {
  useVerdictDetailQuery,
  useVerdictPostmortemQuery,
  useWatchMatchMutation,
} from "@/features/verdict/queries";
import { buildIntelReport } from "@/domain/intel";
import { focusFromDetail, useFocusStore } from "@/features/home/focusStore";
import { errorText } from "@/lib/errors";
import { api } from "@/lib/api";
import { formatDateTime, pct } from "@/lib/format";
import { colors, layout, spacing } from "@/theme/tokens";
import { DetailHero } from "@/features/verdict/components/DetailHero";
import { GateDetailsCard } from "@/features/verdict/components/GateDetailsCard";
import { IntelSection } from "@/features/verdict/components/IntelSection";
import { EvidenceList } from "@/features/verdict/components/EvidenceList";
import { DetailActionBar } from "@/features/verdict/components/DetailActionBar";
import { BetSheet } from "@/features/verdict/components/BetSheet";
import { SealSheet } from "@/features/verdict/components/SealSheet";

export default function VerdictDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const { copy, id: personaId } = usePersonaContent();
  const session = useAuthStore((s) => s.session);
  const [betOpen, setBetOpen] = useState(false);
  const [sealOpen, setSealOpen] = useState(false);
  const setFocus = useFocusStore((s) => s.setFocus);

  const detailQuery = useVerdictDetailQuery(id);
  const detail = detailQuery.data;
  const betsQuery = useBetsQuery(Boolean(session));
  const meQuery = useMeQuery(Boolean(session?.userId));
  const watchQuery = useWatchQuery();
  const postmortemQuery = useVerdictPostmortemQuery(detail?.id);
  const watchMutation = useWatchMatchMutation();
  const shareMutation = useShareVerdictMutation();

  const betExists = Boolean(detail && (betsQuery.data ?? []).some((bet) => bet.verdictId === detail.id));
  const me = meQuery.data;
  const you = me
    ? {
        userId: me.userId,
        rested: me.streak.rested,
        restedUntil: me.streak.restedUntil,
        protectionActive: me.streak.active,
        streak: me.streak.streak,
        disciplineOn: me.disciplineOn,
      }
    : null;
  const watch = detail ? (watchQuery.data ?? []).find((item) => item.targetId === detail.matchId) : undefined;

  const share = async () => {
    if (!detail || shareMutation.isPending) return;
    try {
      const card = await shareMutation.mutateAsync({ verdictId: detail.id, persona: personaId });
      const web = card.url.startsWith("http")
        ? card.url
        : `${api.baseUrl.replace(/\/$/, "")}${card.url}`;
      await Share.share({ message: `${card.text}\n${web}\n${card.deep_link}` });
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  if (detailQuery.isLoading) {
    return (
      <AppScreen bottom={false}>
        <AppHeader title="完整预测" showAssistant={false} onBack={() => goBackOr(router)} />
        <View style={styles.loading}>
          <Skeleton height={320} radius={26} />
          <Skeleton height={150} radius={20} style={{ marginTop: spacing.base }} />
          <Skeleton height={120} radius={20} style={{ marginTop: spacing.base }} />
        </View>
      </AppScreen>
    );
  }

  if (!detail) {
    return (
      <AppScreen bottom={false}>
        <AppHeader title="完整预测" showAssistant={false} onBack={() => goBackOr(router)} />
        <View style={styles.loading}>
          <ErrorState
            message={detailQuery.isError ? errorText(detailQuery.error) : "这场预测不存在或已下线。"}
            onRetry={() => detailQuery.refetch()}
          />
        </View>
      </AppScreen>
    );
  }

  const pm = postmortemQuery.data;
  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="完整预测"
        subtitle={`${detail.home} vs ${detail.away}`}
        showAssistant={false}
        onBack={() => goBackOr(router)}
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {detailQuery.isError ? (
          <ErrorState
            compact
            message="刷新失败，先显示上次的完整预测。"
            onRetry={() => detailQuery.refetch()}
          />
        ) : null}
        <DetailHero detail={detail} onSeal={() => setSealOpen(true)} />
        <IntelSection report={buildIntelReport(detail)} />
        <GateDetailsCard detail={detail} />
        <EvidenceList items={detail.evidence} cutoff={detail.dataCutoff} />

        <Card style={styles.counter}>
          <Text variant="h3">反方怎么看</Text>
          <Text variant="small" color={colors.muted} style={styles.counterText}>
            {detail.status === "promoted"
              ? `这场的预测概率是 ${pct(detail.pick?.prob)}，不是「稳」。单场完全可能落在少数侧；如果临场首发或资金方向反转，预测会重算并另做封存。`
              : "不出预测，不代表它不会赢。是我们算不清它会不会赢——算不清就不预测。你可以看三关里到底缺哪一块。"}
          </Text>
          <Text variant="caption" color={colors.subtle} style={styles.counterText}>
            AI 只做情景与风险解释；最终数字来自统计模型，所有输入都带截止时间。
          </Text>
        </Card>

        {pm && pm.kind === "promoted" ? (
          <Card style={styles.counter}>
            <Text variant="h3">赛后复盘</Text>
            <Text variant="small" color={colors.muted} style={styles.counterText}>
              {pm.attribution?.class ?? "待归因"} · {pm.attribution?.note ?? pm.whatIf}
            </Text>
          </Card>
        ) : null}

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          {copy.footer}
        </Text>
        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          封存时间 {detail.sealedAt ? formatDateTime(detail.sealedAt) : "未封存"} · 引擎 {detail.engine || "预测引擎 v3"}
        </Text>
      </ScrollView>

      <DetailActionBar
        detail={detail}
        betExists={betExists}
        watching={Boolean(watch)}
        onBet={() => setBetOpen(true)}
        onWhyNot={() =>
          router.push({ pathname: "/match/[id]", params: { id: detail.matchId, date: detail.tradeDate } })
        }
        onWatch={async () => {
          if (watchMutation.isPending) return;
          try {
            await watchMutation.mutateAsync({
              targetId: detail.matchId,
              watching: Boolean(watch),
              watchId: watch?.id,
            });
            toast.show(watch ? "已取消关注" : "已关注，停售和终场会提醒", "success");
          } catch (e) {
            toast.show(errorText(e), "error");
          }
        }}
        onShare={share}
        onFocus={() => {
          setFocus(focusFromDetail(detail));
          router.navigate("/(tabs)");
        }}
      />

      <BetSheet
        visible={betOpen}
        verdict={detail}
        you={you}
        onClose={() => setBetOpen(false)}
        onRecorded={() => void betsQuery.refetch()}
      />
      <SealSheet
        visible={sealOpen}
        verdictId={detail.id}
        sealed={Boolean(detail.sealedAt)}
        onClose={() => setSealOpen(false)}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    paddingBottom: 120,
  },
  loading: { padding: layout.pagePadding },
  counter: { marginTop: spacing.base, gap: spacing.xs },
  counterText: { lineHeight: 20 },
  footer: { marginTop: spacing.xl, lineHeight: 18 },
});
