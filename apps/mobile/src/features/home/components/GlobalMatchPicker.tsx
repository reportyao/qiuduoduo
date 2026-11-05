import { useMemo } from "react";
import { useRouter } from "expo-router";
import { currentTradeDateCn } from "@/lib/format";
import { useFloatingStore } from "@/features/assistant/floatingStore";
import { focusFromOnSale, focusFromVerdict, useFocusStore } from "../focusStore";
import { flattenStream, useOnSaleQuery, useStreamQuery } from "../queries";
import { MatchPickerSheet } from "./MatchPickerSheet";

/**
 * 4 个 Tab 共用的一层「今日比赛」弹层。
 * 悬浮头像在任意 Tab 点开它，用的都是同一份数据和同一个导航逻辑。
 */
export function GlobalMatchPicker() {
  const router = useRouter();
  const visible = useFloatingStore((s) => s.pickerOpen);
  const close = useFloatingStore((s) => s.closePicker);
  const setFocus = useFocusStore((s) => s.setFocus);
  const date = currentTradeDateCn();
  const streamQuery = useStreamQuery(date, visible);
  const onsaleQuery = useOnSaleQuery(visible);

  const { page: stream, verdicts } = useMemo(() => {
    const pages = streamQuery.data?.pages ?? [];
    if (pages.length === 0) return { page: null, verdicts: [] };
    return flattenStream(pages);
  }, [streamQuery.data]);

  const onsale = onsaleQuery.data ?? stream?.onsale ?? [];

  return (
    <MatchPickerSheet
      visible={visible}
      onClose={close}
      verdicts={verdicts}
      streamDate={stream?.tradeDate ?? date}
      onsale={onsale}
      loading={streamQuery.isLoading || onsaleQuery.isLoading}
      onSelectVerdict={(id) => {
        const verdict = verdicts.find((item) => item.id === id);
        if (verdict) {
          setFocus(focusFromVerdict(verdict, stream?.tradeDate ?? date));
        } else {
          const match = onsale.find((item) => item.verdictId === id);
          if (match) setFocus(focusFromOnSale(match, stream?.tradeDate ?? date));
          else {
            close();
            router.push({ pathname: "/verdict/[id]", params: { id } });
            return;
          }
        }
        close();
        router.navigate("/(tabs)");
      }}
      onSelectMatch={(matchId, tradeDate) => {
        const match = onsale.find((item) => item.matchId === matchId);
        if (match) setFocus(focusFromOnSale(match, tradeDate || date));
        else {
          close();
          router.push({ pathname: "/match/[id]", params: { id: matchId, date: tradeDate || date } });
          return;
        }
        close();
        router.navigate("/(tabs)");
      }}
    />
  );
}
