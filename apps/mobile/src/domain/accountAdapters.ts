import type {
  AppVersionInfo,
  BetRecord,
  ChatCard,
  InboxItem,
  InboxResponse,
  LedgerItem,
  LedgerResponse,
  LegalText,
  MeProfile,
  NotifySettings,
  Postmortem,
  WatchItem,
  WeeklyReport,
} from "./types";
import { normalizePersona } from "@/features/personas/personaIds";
import { utcIso } from "@/lib/format";
import type { OddsFormat } from "@/features/preferences/prefsStore";
import {
  array,
  boolean,
  nullableNumber,
  nullableString,
  number,
  numberRecord,
  record,
  string,
} from "@/lib/parse";

function oddsFormat(value: unknown): OddsFormat {
  return value === "decimal" || value === "hk" || value === "indo" || value === "american"
    ? value
    : "decimal";
}

export function adaptMe(value: unknown): MeProfile | null {
  const raw = record(value);
  const userId = string(raw.user_id ?? raw.userId);
  if (!userId) return null;
  const streak = record(raw.streak);
  return {
    userId,
    displayName: string(raw.display_name ?? raw.displayName, "解球用户"),
    persona: normalizePersona(raw.persona),
    oddsFormat: oddsFormat(raw.odds_format ?? raw.oddsFormat),
    locale: string(raw.locale, "zh"),
    region: string(raw.region, "cn"),
    disciplineOn: boolean(raw.discipline_on ?? raw.disciplineOn, true),
    phone: nullableString(raw.phone),
    email: nullableString(raw.email),
    streak: {
      streak: number(streak.streak),
      active: boolean(streak.active),
      threshold: number(streak.threshold, 3),
      rested: boolean(streak.rested),
      restedUntil: string(streak.rested_until),
      disciplineOn: boolean(streak.discipline_on, true),
    },
    restedUntil: string(raw.rested_until),
    memories: array(raw.memories).map((entry) => {
      const item = record(entry);
      return {
        key: string(item.key),
        value: string(item.value),
        source: string(item.source, "你说过"),
      };
    }),
  };
}

export function adaptBets(value: unknown): BetRecord[] {
  return array(value).map((entry) => {
    const item = record(entry);
    return {
      id: number(item.id),
      verdictId: string(item.verdict_id),
      match: string(item.match),
      matchNo: string(item.match_no),
      amount: number(item.amount),
      pool: string(item.pool, "had"),
      goalLine: nullableString(item.goal_line),
      sp: nullableNumber(item.sp),
      pickDir: string(item.pick_dir),
      status: string(item.status),
      settled: item.settled === "win" || item.settled === "lose" ? item.settled : null,
      resultScore: nullableString(item.result_score),
      pnl: nullableNumber(item.pnl),
    };
  });
}

export function adaptWeekly(value: unknown): WeeklyReport {
  const raw = record(value);
  const killed = record(raw.killed);
  const you = record(raw.you);
  return {
    rangeDays: number(raw.range_days, 7),
    verdictsTotal: number(raw.verdicts_total),
    promoted: number(raw.promoted),
    settled: number(raw.settled),
    wins: number(raw.wins),
    attribution: numberRecord(raw.attribution),
    killed: {
      rangeDays: number(killed.range_days, 7),
      killedTotal: number(killed.killed_total),
      settled: number(killed.settled),
      wouldLose: number(killed.would_lose),
      wouldWin: number(killed.would_win),
      avoidedLossCny: number(killed.avoided_loss_cny),
      missedWinCny: number(killed.missed_win_cny),
    },
    you:
      Object.keys(you).length > 0
        ? {
            bets: number(you.bets),
            settledBets: number(you.settled_bets),
            pnl: number(you.pnl),
            attribution: numberRecord(you.attribution),
          }
        : null,
  };
}

export function adaptLedger(value: unknown): LedgerResponse {
  const raw = record(value);
  const stats = record(raw.stats);
  return {
    items: array(raw.items).map((entry): LedgerItem => {
      const item = record(entry);
      const pickRaw = record(item.pick);
      return {
        id: string(item.id),
        tradeDate: string(item.trade_date),
        matchNo: string(item.match_no),
        match: string(item.match),
        league: string(item.league),
        kickoff: string(item.kickoff),
        pool: string(item.pool),
        goalLine: nullableString(item.goal_line),
        pick: Object.keys(pickRaw).length > 0 ? { dir: nullableString(pickRaw.dir) } : null,
        status: string(item.status),
        settled: item.settled === "win" || item.settled === "lose" ? item.settled : null,
        resultScore: nullableString(item.result_score),
        hash: string(item.hash),
      };
    }),
    stats: {
      promotedTotal: number(stats.promoted_total),
      settled: number(stats.settled),
      wins: number(stats.wins),
      losses: number(stats.losses),
      currentLosingStreak: number(stats.current_losing_streak),
    },
  };
}

export function adaptPostmortem(value: unknown): Postmortem {
  const raw = record(value);
  const attribution = record(raw.attribution);
  const bet = record(raw.bet);
  const pickRaw = record(raw.pick);
  return {
    id: string(raw.id),
    matchNo: string(raw.match_no),
    match: string(raw.match),
    tradeDate: string(raw.trade_date),
    pool: string(raw.pool),
    goalLine: nullableString(raw.goal_line),
    pick:
      Object.keys(pickRaw).length > 0
        ? {
            dir: nullableString(pickRaw.dir),
            prob: nullableNumber(pickRaw.prob),
            sp: nullableNumber(pickRaw.sp),
          }
        : null,
    status: string(raw.status),
    settled: raw.settled === "win" || raw.settled === "lose" ? raw.settled : null,
    resultScore: nullableString(raw.result_score),
    kind: string(raw.kind),
    deadGate:
      raw.dead_gate === "price" || raw.dead_gate === "market" || raw.dead_gate === "model"
        ? raw.dead_gate
        : null,
    why: record(raw.why),
    whatIf: string(raw.whatif),
    attribution:
      Object.keys(attribution).length > 0
        ? {
            settled: boolean(attribution.settled),
            class: nullableString(attribution.class),
            note: string(attribution.note),
          }
        : undefined,
    bet:
      Object.keys(bet).length > 0
        ? {
            amount: number(bet.amount),
            pickDir: string(bet.pick_dir),
            pnl: nullableNumber(bet.pnl),
            sp: nullableNumber(bet.sp),
          }
        : undefined,
  };
}

export function adaptInbox(value: unknown): InboxResponse {
  const raw = record(value);
  return {
    unread: number(raw.unread),
    items: array(raw.items).map((entry): InboxItem => {
      const item = record(entry);
      return {
        id: number(item.id),
        eventId: nullableNumber(item.event_id),
        title: string(item.title),
        body: string(item.body),
        deepLink: nullableString(item.deeplink),
        createdAt: utcIso(string(item.created_at)) ?? "",
        openedAt: nullableString(item.opened_at),
        clickedAt: nullableString(item.clicked_at),
      };
    }),
  };
}

export function adaptWatch(value: unknown): WatchItem[] {
  const raw = record(value);
  return array(raw.items).map((entry) => {
    const item = record(entry);
    return {
      id: number(item.id),
      targetType: string(item.target_type),
      targetId: string(item.target_id),
      events: array(item.events).filter((v): v is string => typeof v === "string"),
      matchNo: nullableString(item.match_no),
      home: nullableString(item.home),
      away: nullableString(item.away),
      league: nullableString(item.league),
      kickoff: nullableString(item.kickoff),
    };
  });
}

export function adaptNotify(value: unknown): NotifySettings {
  const raw = record(value);
  return {
    channels: array(raw.channels).filter((v): v is string => typeof v === "string"),
    eventTypes: array(raw.event_types).filter((v): v is string => typeof v === "string"),
    quietStart: string(raw.quiet_start, "23:30"),
    quietEnd: string(raw.quiet_end, "08:00"),
    dailyCap: number(raw.daily_cap, 2),
    paused: boolean(raw.paused),
  };
}

export function adaptChat(value: unknown): ChatCard {
  const raw = record(value);
  const card: ChatCard = {
    type: string(raw.type, "fallback"),
    text: string(raw.text, "我在。可以问今晚、为什么不推、复盘或我的记忆。"),
    verdictId: nullableString(raw.verdict_id) ?? undefined,
    deadGate: nullableString(raw.dead_gate) ?? undefined,
  };
  const memories = array(raw.memories).map((entry) => {
    const item = record(entry);
    return {
      key: string(item.key),
      value: string(item.value),
      source: string(item.source, "你说过"),
    };
  });
  if (memories.length > 0) card.memories = memories;
  const protection = record(raw.protection);
  if (Object.keys(protection).length > 0) {
    card.protection = {
      streak: number(protection.streak),
      active: boolean(protection.active),
    };
  }
  const memory = record(raw.memory);
  if (Object.keys(memory).length > 0) {
    card.memory = {
      key: string(memory.key),
      value: string(memory.value),
      status: string(memory.status),
    };
  }
  const conflict = record(raw.conflict);
  if (Object.keys(conflict).length > 0) {
    card.conflict = {
      key: string(conflict.key),
      existing: string(conflict.existing),
      incoming: string(conflict.incoming),
    };
  }
  const postmortem = record(raw.postmortem);
  if (Object.keys(postmortem).length > 0) {
    card.postmortem = adaptPostmortem(postmortem);
  }
  return card;
}

export function adaptLegal(value: unknown): LegalText {
  const raw = record(value);
  return {
    region: string(raw.region, "cn"),
    helpline: string(raw.helpline),
    compliance: string(raw.compliance),
    minAge: number(raw.min_age, 18),
    dataSource: string(raw.data_source),
  };
}

export function adaptVersion(value: unknown): AppVersionInfo {
  const raw = record(value);
  return {
    api: string(raw.api),
    minAppVersion: string(raw.min_app_version),
    forceUpdateBelow: string(raw.force_update_below),
    freezeMode: boolean(raw.freeze_mode),
  };
}
