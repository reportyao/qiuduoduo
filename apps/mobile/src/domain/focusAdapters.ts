import { array, nullableNumber, nullableString, record, string } from "@/lib/parse";
import type { SportmonksIntelData } from "./types";
import { adaptSportmonksIntel } from "./sportmonksAdapters";

export interface FocusCoverageSource {
  key: string;
  status: string;
  lastSync: string | null;
  coverage: number;
}

export interface FocusCoverage {
  score: number;
  level: string;
  deepEligible: boolean;
  missing: string[];
  sources: FocusCoverageSource[];
  minutesToClose: number | null;
  hoursToKickoff: number | null;
}

export interface FocusFact {
  id: string;
  kind: string;
  label: string;
  value: string;
  detail: string;
  source: string | null;
  capturedAt: string | null;
  status: string;
  confidence: number | null;
}

export interface FocusCapabilities {
  canBet: boolean;
  betRequiresConfirm: boolean;
  canWatch: boolean;
  watching: boolean;
  canWhyNot: boolean;
  canViewDetail: boolean;
  canShare: boolean;
  canRest: boolean;
  canRemindLineup: boolean;
  canRefresh: boolean;
}

export interface FocusAction {
  id: string;
  enabled: boolean;
  primary: boolean;
  requiresAuth: boolean;
  reason: string | null;
}

export interface MatchFocus {
  matchId: string;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  saleClose: string;
  state: string;
  tradeDate: string;
  requestId: string;
  asOf: string;
  coverage: FocusCoverage;
  facts: FocusFact[];
  unknowns: string[];
  capabilities: FocusCapabilities;
  actions: FocusAction[];
  verdictId: string | null;
  sportmonks?: SportmonksIntelData | null;
}

export interface PulseCounts {
  matches: number;
  spSnapshots: number;
  intlOdds: number;
  modelRuns: number;
  verdicts: number;
  revisions: number;
  intelItems: number;
  sealedLinks: number;
  lineups: number;
  injuries: number;
  standings: number;
  sportmonksIntel?: number;
  sportmonksLineups?: number;
  sportmonksStandings?: number;
  sportmonksPredictionTypes?: number;
}

export interface PulseSource {
  key: string;
  label: string;
  status: string;
  lastSync: string | null;
  coverage: number;
}

export interface Pulse {
  tradeDate: string;
  asOf: string;
  staleSeconds: number | null;
  counts: PulseCounts;
  dataPoints: number;
  display: { dataPoints: number; factor: number; unit: string };
  allTime: { dataPoints: number; matches: number; sealed: number };
  stages: { key: string; label: string; count: number; status: string }[];
  sources: PulseSource[];
  outcomes: { promoted: number; screening: number; killed: number };
  excluded: number;
  definition: string;
}

function adaptCoverage(value: unknown): FocusCoverage {
  const raw = record(value);
  return {
    score: Number(raw.score ?? 0),
    level: string(raw.level ?? "unknown"),
    deepEligible: Boolean(raw.deep_eligible),
    missing: array(raw.missing).map(String),
    sources: array(raw.sources).map((entry) => {
      const item = record(entry);
      return {
        key: string(item.key),
        status: string(item.status),
        lastSync: nullableString(item.last_sync),
        coverage: Number(item.coverage ?? 0),
      };
    }),
    minutesToClose: nullableNumber(raw.minutes_to_close),
    hoursToKickoff: nullableNumber(raw.hours_to_kickoff),
  };
}

function adaptCapabilities(value: unknown): FocusCapabilities {
  const raw = record(value);
  return {
    canBet: Boolean(raw.can_bet),
    betRequiresConfirm: Boolean(raw.bet_requires_confirm),
    canWatch: Boolean(raw.can_watch),
    watching: Boolean(raw.watching),
    canWhyNot: Boolean(raw.can_why_not),
    canViewDetail: Boolean(raw.can_view_detail),
    canShare: Boolean(raw.can_share),
    canRest: Boolean(raw.can_rest),
    canRemindLineup: Boolean(raw.can_remind_lineup),
    canRefresh: Boolean(raw.can_refresh),
  };
}

export function adaptFocus(value: unknown): MatchFocus | null {
  const raw = record(value);
  const match = record(raw.match);
  const matchId = string(match.match_id);
  if (!matchId) return null;
  return {
    matchId,
    matchNo: string(match.match_no),
    league: string(match.league),
    home: string(match.home),
    away: string(match.away),
    kickoff: string(match.kickoff),
    saleClose: string(match.sale_close ?? match.kickoff),
    state: string(raw.state),
    tradeDate: string(raw.trade_date),
    requestId: string(raw.request_id),
    asOf: string(raw.as_of),
    coverage: adaptCoverage(raw.coverage),
    facts: array(record(raw.intel).facts).map((entry) => {
      const item = record(entry);
      return {
        id: string(item.id),
        kind: string(item.kind),
        label: string(item.label),
        value: string(item.value),
        detail: string(item.detail),
        source: nullableString(item.source),
        capturedAt: nullableString(item.captured_at),
        status: string(item.status),
        confidence: nullableNumber(item.confidence),
      };
    }),
    unknowns: array(record(raw.intel).unknowns).map(String),
    capabilities: adaptCapabilities(raw.capabilities),
    actions: array(raw.actions).map((entry) => {
      const item = record(entry);
      return {
        id: string(item.id),
        enabled: Boolean(item.enabled),
        primary: Boolean(item.primary),
        requiresAuth: Boolean(item.requires_auth),
        reason: nullableString(item.reason),
      };
    }),
    verdictId: nullableString(record(raw.verdict).id),
    sportmonks: adaptSportmonksIntel(record(raw.intel).sportmonks),
  };
}

export function adaptPulse(value: unknown): Pulse {
  const raw = record(value);
  const counts = record(raw.counts);
  const display = record(raw.display);
  const allTime = record(raw.all_time);
  const outcomes = record(raw.outcomes);
  return {
    tradeDate: string(raw.trade_date),
    asOf: string(raw.as_of),
    staleSeconds: nullableNumber(raw.stale_seconds),
    counts: {
      matches: Number(counts.matches ?? 0),
      spSnapshots: Number(counts.sp_snapshots ?? 0),
      intlOdds: Number(counts.intl_odds ?? 0),
      modelRuns: Number(counts.model_runs ?? 0),
      verdicts: Number(counts.verdicts ?? 0),
      revisions: Number(counts.revisions ?? 0),
      intelItems: Number(counts.intel_items ?? 0),
      sealedLinks: Number(counts.sealed_links ?? 0),
      lineups: Number(counts.lineups ?? 0),
      injuries: Number(counts.injuries ?? 0),
      standings: Number(counts.standings ?? 0),
      sportmonksIntel: Number(counts.sportmonks_intel ?? 0),
      sportmonksLineups: Number(counts.sportmonks_lineups ?? 0),
      sportmonksStandings: Number(counts.sportmonks_standings ?? 0),
      sportmonksPredictionTypes: Number(counts.sportmonks_prediction_types ?? 0),
    },
    dataPoints: Number(raw.data_points ?? 0),
    display: {
      dataPoints: Number(display.data_points ?? 0),
      factor: Number(display.factor ?? 1),
      unit: string(display.unit ?? "数据点"),
    },
    allTime: {
      dataPoints: Number(allTime.data_points ?? 0),
      matches: Number(allTime.matches ?? 0),
      sealed: Number(allTime.sealed ?? 0),
    },
    stages: array(raw.stages).map((entry) => {
      const item = record(entry);
      return {
        key: string(item.key),
        label: string(item.label),
        count: Number(item.count ?? 0),
        status: string(item.status),
      };
    }),
    sources: array(raw.sources).map((entry) => {
      const item = record(entry);
      return {
        key: string(item.key),
        label: string(item.label),
        status: string(item.status),
        lastSync: nullableString(item.last_sync),
        coverage: Number(item.coverage ?? 0),
      };
    }),
    outcomes: {
      promoted: Number(outcomes.promoted ?? 0),
      screening: Number(outcomes.screening ?? 0),
      killed: Number(outcomes.killed ?? 0),
    },
    excluded: Number(raw.excluded ?? 0),
    definition: string(raw.definition),
  };
}
