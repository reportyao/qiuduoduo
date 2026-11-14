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
import { useRecommendationsTodayQuery } from "@/features/home/queries";
import { useMeQuery } from "@/features/account/queries";
import { useWatchQuery } from "@/features/inbox/queries";
import { useShareVerdictMutation } from "@/features/assistant/queries";
import {
  useVerdictDetailQuery,
  useVerdictPostmortemQuery,
  useWatchMatchMutation,
} from "@/features/verdict/queries";
import { focusFromDetail, useFocusStore } from "@/features/home/focusStore";
import { useParlayStore } from "@/features/tools/parlayStore";
import { toParlayDir } from "@/features/tools/parlayDirection";
import { errorText } from "@/lib/errors";
import { api } from "@/lib/api";
import { currentTradeDateCn, formatDateTime } from "@/lib/format";
import { colors, layout, spacing } from "@/theme/tokens";
import { DetailHero } from "@/features/verdict/components/DetailHero";
import { ProbabilityCompareCard } from "@/features/verdict/components/ProbabilityCompare";
import { AiIntelCard } from "@/features/verdict/components/AiIntelCard";
import { SportmonksIntelSection } from "@/features/verdict/components/SportmonksIntelSection";
import { MatchAnalysisCard } from "@/features/verdict/components/MatchAnalysisCard";
import { EvidenceChainCard } from "@/features/verdict/components/EvidenceChainCard";
import { DetailActionBar } from "@/features/verdict/components/DetailActionBar";
import { DetailSectionTabs, type DetailSection } from "@/features/verdict/components/DetailSectionTabs";
import { BetSheet } from "@/features/verdict/components/BetSheet";
import { SealSheet } from "@/features/verdict/components/SealSheet";

export default function VerdictDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const { copy, id: personaId } = usePersonaContent();
  const session = useAuthStore((s) => s.session);
  const [section, setSection] = useState<DetailSection>("overview");
  const [betOpen, setBetOpen] = useState(false);
  const [sealOpen, setSealOpen] = useState(false);
  const setFocus = useFocusStore((s) => s.setFocus);
  const parlayLegs = useParlayStore((s) => s.legs);
  const addParlayLeg = useParlayStore((s) => s.add);

  const detailQuery = useVerdictDetailQuery(id);
  const detail = detailQuery.data;
  const publishedQuery = useRecommendationsTodayQuery(
    detail?.tradeDate ?? currentTradeDateCn(),
    Boolean(detail),
  );
  const published = publishedQuery.isSuccess
    ? publishedQuery.data.snapshots.some((snapshot) => snapshot.verdict?.id === detail?.id)
    : null;
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

  const addToParlay = () => {
    if (!detail) return;
    const dir = toParlayDir(detail.pick?.dir);
    if (!dir) {
      toast.show("这场还没有预测方向，暂时不能加入串关", "warning");
      return;
    }
    const odds = detail.pick?.sp
      ?? (dir === "home" ? detail.sp.h : dir === "draw" ? detail.sp.d : detail.sp.a);
    if (!odds || odds <= 1) {
      toast.show("这场赔率还不完整，暂时不能加入串关", "warning");
      return;
    }
    const result = addParlayLeg({
      verdictId: detail.id,
      matchId: detail.matchId,
      tradeDate: detail.tradeDate,
      home: detail.home,
      away: detail.away,
      kickoff: detail.kickoff,
      dir,
      odds,
      rake: detail.rake,
      marketOnly: detail.status !== "promoted"
        || !Array.isArray(detail.model?.shrunk)
        || detail.model.shrunk.length !== 3,
    });
    if (!result.ok) {
      toast.show(result.reason ?? "加入串关失败", "warning");
    } else {
      toast.show("已加入串关，最多 6 场", "success");
    }
    router.push({
      pathname: "/tools/parlay",
      params: { seed: String(Date.now()), date: detail.tradeDate },
    });
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
        <DetailHero detail={detail} published={published} onSeal={() => setSealOpen(true)} />
        <DetailSectionTabs value={section} onChange={setSection} />

        {section === "overview" ? (
          <>
            <EvidenceChainCard items={detail.evidence} cutoff={detail.dataCutoff} />
            {detail.aiResearch ? <AiIntelCard data={detail.aiResearch} /> : null}
          </>
        ) : null}

        {section === "predictions" ? (
          <SportmonksIntelSection data={detail.sportmonksIntel} />
        ) : null}

        {section === "markets" ? (
          <>
            {detail.probabilityCompare ? (
              <ProbabilityCompareCard data={detail.probabilityCompare} />
            ) : null}
            <MatchAnalysisCard matchId={detail.matchId} date={detail.tradeDate} />
          </>
        ) : null}

        {section === "review" ? (
          <>
            {pm && pm.kind === "promoted" ? (
              <Card style={styles.counter}>
                <Text variant="h3">赛后复盘</Text>
                <Text variant="small" color={colors.muted} style={styles.counterText}>
                  {pm.attribution?.class ?? "待归因"} · {pm.attribution?.note ?? pm.whatIf}
                </Text>
              </Card>
            ) : (
              <Card style={styles.counter}>
                <Text variant="h3">赛后复盘</Text>
                <Text variant="small" color={colors.muted} style={styles.counterText}>
                  赛果未出或暂无复盘；开球并结算后这里会给出归因。
                </Text>
              </Card>
            )}
          </>
        ) : null}

        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          {copy.footer}
        </Text>
        <Text variant="caption" color={colors.subtle} center style={styles.footer}>
          封存时间 {detail.sealedAt ? formatDateTime(detail.sealedAt) : "未封存"} · 模型 {detail.engine || "模型 v3"}
        </Text>
      </ScrollView>

      <DetailActionBar
        detail={detail}
        published={published}
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
        onParlay={addToParlay}
        parlayAdded={parlayLegs.some((leg) => leg.verdictId === detail.id)}
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
    paddingBottom: 168,
  },
  loading: { padding: layout.pagePadding },
  counter: { marginTop: spacing.base, gap: spacing.xs },
  counterText: { lineHeight: 20 },
  footer: { marginTop: spacing.xl, lineHeight: 18 },
});
