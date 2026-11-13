import { useMemo } from "react";
import { useRouter } from "expo-router";
import { currentTradeDateCn } from "@/lib/format";
import { useFloatingStore } from "@/features/assistant/floatingStore";
import { useHomeSelectionStore } from "../homeSelectionStore";
import { flattenStream, useOnSaleQuery, useStreamQuery } from "../queries";
import { MatchPickerSheet } from "./MatchPickerSheet";
import type { BriefMatchOption } from "./BriefMatchPicker";
import type { OnSaleItem, VerdictSummary } from "@/domain/types";

function optionFromVerdict(verdict: VerdictSummary): BriefMatchOption {
  return {
    matchId: verdict.matchId,
    verdictId: verdict.id,
    matchNo: verdict.matchNo,
    league: verdict.league,
    home: verdict.home,
    away: verdict.away,
    kickoff: verdict.kickoff,
    status: verdict.status,
    tier: verdict.tier ?? null,
  };
}

function optionFromMatch(match: OnSaleItem): BriefMatchOption {
  return {
    matchId: match.matchId,
    verdictId: match.verdictId ?? null,
    matchNo: match.matchNo,
    league: match.league,
    home: match.home,
    away: match.away,
    kickoff: match.kickoff,
    status: match.status,
    tier: match.tier ?? null,
    coverage: match.coverage,
  };
}

/**
 * 4 个 Tab 共用的一层「今日比赛」弹层。
 * 选中后统一交给首页消费：切日期、聚焦、追加「看这场」消息卡。
 */
export function GlobalMatchPicker() {
  const router = useRouter();
  const visible = useFloatingStore((s) => s.pickerOpen);
  const close = useFloatingStore((s) => s.closePicker);
  const requestSelection = useHomeSelectionStore((s) => s.request);
  const date = currentTradeDateCn();
  const streamQuery = useStreamQuery(date, visible);
  const onsaleQuery = useOnSaleQuery(visible);

  const { page: stream, verdicts } = useMemo(() => {
    const pages = streamQuery.data?.pages ?? [];
    if (pages.length === 0) return { page: null, verdicts: [] as VerdictSummary[] };
    return flattenStream(pages);
  }, [streamQuery.data]);

  const onsale = onsaleQuery.data ?? stream?.onsale ?? [];
  const tradeDate = stream?.tradeDate ?? date;

  const selectVerdict = (id: string) => {
    const verdict = verdicts.find((item) => item.id === id);
    const match = onsale.find((item) => item.verdictId === id) ?? null;
    if (!verdict && !match) {
      close();
      router.push({ pathname: "/verdict/[id]", params: { id } });
      return;
    }
    requestSelection({
      option: verdict ? optionFromVerdict(verdict) : optionFromMatch(match as OnSaleItem),
      verdict: verdict ?? null,
      match,
      tradeDate,
    });
    close();
    router.navigate("/(tabs)");
  };

  const selectMatch = (matchId: string, matchDate: string) => {
    const match = onsale.find((item) => item.matchId === matchId);
    if (!match) {
      close();
      router.push({
        pathname: "/match/[id]",
        params: { id: matchId, date: matchDate || date },
      });
      return;
    }
    requestSelection({
      option: optionFromMatch(match),
      verdict: null,
      match,
      tradeDate: matchDate || date,
    });
    close();
    router.navigate("/(tabs)");
  };

  return (
    <MatchPickerSheet
      visible={visible}
      onClose={close}
      verdicts={verdicts}
      streamDate={tradeDate}
      onsale={onsale}
      loading={streamQuery.isLoading || onsaleQuery.isLoading}
      onSelectVerdict={selectVerdict}
      onSelectMatch={selectMatch}
    />
  );
}
