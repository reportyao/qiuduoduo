import type { RecommendationReview, VerdictSummary } from "./types";
import { adaptVerdictSummary } from "./streamAdapters";
import { array, nullableString, record, string } from "@/lib/parse";

export interface RecommendationSnapshot {
  snapshotId: string;
  tradeDate: string;
  matchId: string;
  status: string;
  version: number;
  payloadHash: string;
  publishedAt: string | null;
  expiresAt: string | null;
  verdict: VerdictSummary | null;
  direction: string;
  confidence: number | null;
  probLow: number | null;
  probHigh: number | null;
  intervalStatus: string | null;
  conditions: string[];
  invalidators: string[];
  review: RecommendationReview | null;
}

export interface RecommendationPlan {
  planId: string;
  tradeDate: string;
  riskProfile: string;
  label: string;
  legs: string[];
  status: string;
  version: number;
  payloadHash: string;
  publishedAt: string | null;
  expiresAt: string | null;
  check: Record<string, unknown>;
  note: string | null;
  conditions: string[];
  invalidators: string[];
  review: RecommendationReview | null;
}

export interface RecommendationToday {
  tradeDate: string;
  generatedAt: string;
  snapshots: RecommendationSnapshot[];
  plans: RecommendationPlan[];
  verdicts: VerdictSummary[];
  message: string | null;
}

export function adaptRecommendationToday(value: unknown): RecommendationToday {
  const raw = record(value);
  const snapshots = array(raw.snapshots).map((entry): RecommendationSnapshot => {
    const item = record(entry);
    return {
      snapshotId: string(item.snapshot_id),
      tradeDate: string(item.trade_date),
      matchId: string(item.match_id),
      status: string(item.status),
      version: Number(item.version ?? 1),
      payloadHash: string(item.payload_hash),
      publishedAt: nullableString(item.published_at),
      expiresAt: nullableString(item.expires_at),
      verdict: adaptVerdictSummary(item.verdict),
      direction: string(item.direction ?? "观望"),
      confidence: typeof item.confidence === "number" ? item.confidence : null,
      probLow: typeof item.prob_low === "number" ? item.prob_low : null,
      probHigh: typeof item.prob_high === "number" ? item.prob_high : null,
      intervalStatus: nullableString(item.interval_status),
      conditions: array(item.conditions).map(String),
      invalidators: array(item.invalidators).map(String),
      review: adaptReview(item.review),
    };
  }).filter((item) => item.snapshotId && item.verdict) as RecommendationSnapshot[];
  const plans = array(raw.plans).map((entry): RecommendationPlan => {
    const item = record(entry);
    return {
      planId: string(item.plan_id),
      tradeDate: string(item.trade_date),
      riskProfile: string(item.risk_profile),
      label: string(item.label),
      legs: array(item.legs).map((leg) => String(leg)),
      status: string(item.status),
      version: Number(item.version ?? 1),
      payloadHash: string(item.payload_hash),
      publishedAt: nullableString(item.published_at),
      expiresAt: nullableString(item.expires_at),
      check: record(item.check),
      note: nullableString(item.note),
      conditions: array(item.conditions).map(String),
      invalidators: array(item.invalidators).map(String),
      review: adaptReview(item.review),
    };
  }).filter((item) => item.planId);
  const fromSnapshots = snapshots
    .filter((item) => item.verdict !== null)
    .map((item) => ({
      ...(item.verdict as VerdictSummary),
      snapshotId: item.snapshotId,
      snapshotStatus: item.status,
      direction: item.direction,
      confidence: item.confidence,
      probLow: item.probLow,
      probHigh: item.probHigh,
      intervalStatus: item.intervalStatus,
      conditions: item.conditions,
      invalidators: item.invalidators,
      review: item.review,
    }));
  const verdicts = fromSnapshots.length
    ? fromSnapshots
    : array(raw.verdicts).map(adaptVerdictSummary)
      .filter((item): item is VerdictSummary => item !== null);
  return {
    tradeDate: string(raw.trade_date),
    generatedAt: string(raw.generated_at),
    snapshots,
    plans,
    verdicts,
    message: nullableString(raw.message),
  };
}

function adaptReview(value: unknown): RecommendationReview | null {
  const item = record(value);
  if (!item.status) return null;
  return {
    status: string(item.status),
    reviewer: string(item.reviewer ?? "rules"),
    reviewedAt: nullableString(item.reviewed_at),
    promptVer: string(item.prompt_ver ?? ""),
    llmDegraded: Boolean(item.llm_degraded),
    layers: array(item.layers).map(record),
  };
}
