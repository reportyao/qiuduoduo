import type { OnSaleItem, VerdictSummary } from "@/domain/types";
import { tradeDateCnFromKickoff } from "@/lib/format";
import type { BriefMatchOption } from "./components/BriefMatchPicker";

/** 首页开场选择条：已发布判决 + 当前竞彩日在售，按 matchId 合并、按开赛时间排序。 */
export function buildBriefOptions(
  verdicts: VerdictSummary[],
  references: VerdictSummary[],
  onsale: OnSaleItem[],
  date: string,
): BriefMatchOption[] {
  const byMatch = new Map<string, BriefMatchOption>();
  for (const verdict of verdicts) {
    byMatch.set(verdict.matchId, {
      matchId: verdict.matchId,
      verdictId: verdict.id,
      home: verdict.home,
      away: verdict.away,
      kickoff: verdict.kickoff,
      status: verdict.status,
      tier: verdict.tier ?? null,
    });
  }
  for (const verdict of references) {
    if (!byMatch.has(verdict.matchId)) {
      byMatch.set(verdict.matchId, {
        matchId: verdict.matchId,
        verdictId: verdict.id,
        home: verdict.home,
        away: verdict.away,
        kickoff: verdict.kickoff,
        status: verdict.status,
        tier: verdict.tier ?? "market_reference",
      });
    }
  }
  for (const match of onsale) {
    // 在售接口可能跨销售日；开场只列当前查看的竞彩日。
    if (tradeDateCnFromKickoff(match.kickoff) !== date) continue;
    if (!byMatch.has(match.matchId)) {
      byMatch.set(match.matchId, {
        matchId: match.matchId,
        verdictId: match.verdictId ?? null,
        home: match.home,
        away: match.away,
        kickoff: match.kickoff,
        status: match.status,
        tier: match.tier ?? null,
      });
    }
  }
  return [...byMatch.values()].sort((a, b) => a.kickoff.localeCompare(b.kickoff));
}
