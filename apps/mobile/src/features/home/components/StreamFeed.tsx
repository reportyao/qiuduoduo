import { View } from "react-native";
import type { StreamResponse, VerdictSummary } from "@/domain/types";
import {
  AvoidMessage,
  LoadMore,
  PostmortemMessage,
  UnattendedMessage,
  VerdictMessage,
} from "./ConversationMessages";

/** 首页正常销售日的预测/砍单/复盘消息流；只负责渲染，数据与动作由页面传入。 */
export function StreamFeed({
  stream,
  heroVerdict,
  restVerdicts,
  betIds,
  showRest,
  hasNextPage,
  fetchingNext,
  onOpenVerdict,
  onBet,
  onWhyNot,
  onSeal,
  onParlay,
  onFetchNext,
}: {
  stream: StreamResponse;
  heroVerdict: VerdictSummary | null;
  restVerdicts: VerdictSummary[];
  betIds: Set<string>;
  showRest: boolean;
  hasNextPage: boolean;
  fetchingNext: boolean;
  onOpenVerdict: (id: string) => void;
  onBet: (verdict: VerdictSummary) => void;
  onWhyNot: (matchId: string) => void;
  onSeal: (id: string) => void;
  onParlay: () => void;
  onFetchNext: () => void;
}) {
  return (
    <View>
      {heroVerdict ? (
        <VerdictMessage
          verdict={heroVerdict}
          hero
          betExists={betIds.has(heroVerdict.id)}
          onOpen={onOpenVerdict}
          onBet={onBet}
          onWhyNot={onWhyNot}
          onSeal={onSeal}
          onParlay={onParlay}
        />
      ) : null}

      {showRest
        ? restVerdicts.map((verdict, index) => (
            <VerdictMessage
              key={verdict.id}
              delay={Math.min(index * 45, 360)}
              verdict={verdict}
              betExists={betIds.has(verdict.id)}
              onOpen={onOpenVerdict}
              onBet={onBet}
              onWhyNot={onWhyNot}
              onSeal={onSeal}
            />
          ))
        : null}

      {showRest && hasNextPage ? (
        <LoadMore loading={fetchingNext} onPress={onFetchNext} />
      ) : null}

      <AvoidMessage items={stream.avoid} onOpen={onWhyNot} />
      <PostmortemMessage items={stream.postmortems} onOpen={onOpenVerdict} />
      <UnattendedMessage items={stream.unattended} onOpen={onOpenVerdict} />
    </View>
  );
}
