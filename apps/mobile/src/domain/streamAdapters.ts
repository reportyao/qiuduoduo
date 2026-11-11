import type {
  AvoidItem,
  EvidenceItem,
  GateDetail,
  GateKey,
  GateResult,
  OnSaleItem,
  PostmortemSummary,
  AIResearchData,
  ProbabilityCompareData,
  ProbabilityTriple,
  RestDay,
  SealResponse,
  StreamResponse,
  StreamStats,
  VerdictDetail,
  VerdictPick,
  VerdictSummary,
  WhyNotResponse,
  YouState,
} from "./types";
import { utcIso } from "@/lib/format";
import {
  array,
  boolean,
  nullableNumber,
  nullableString,
  number,
  record,
  string,
  stringArray,
} from "@/lib/parse";

export const EMPTY_STATS: StreamStats = {
  total: 0,
  priceFail: 0,
  pricePass: 0,
  promoted: 0,
  screening: 0,
  gateNote: "",
};

function gateResult(value: unknown): GateResult {
  if (value && typeof value === "object") {
    return gateResult((value as { result?: unknown }).result);
  }
  return value === "pass" || value === "fail" || value === "pending_data" ? value : "unknown";
}

function gateMap(value: unknown): Partial<Record<GateKey, GateResult>> {
  const raw = record(value);
  const out: Partial<Record<GateKey, GateResult>> = {};
  for (const key of ["price", "market", "model"] as GateKey[]) {
    if (raw[key] != null) out[key] = gateResult(raw[key]);
  }
  return out;
}

function gateDetails(value: unknown): Partial<Record<GateKey, GateDetail>> {
  const raw = record(value);
  const out: Partial<Record<GateKey, GateDetail>> = {};
  for (const key of ["price", "market", "model"] as GateKey[]) {
    const entry = record(raw[key]);
    if (Object.keys(entry).length > 0) {
      out[key] = {
        gate: key,
        result: gateResult(entry.result),
        detail: record(entry.detail),
      };
    }
  }
  return out;
}

function probs(value: unknown): ProbabilityTriple {
  const raw = record(value);
  return {
    home: number(raw.home),
    draw: number(raw.draw),
    away: number(raw.away),
  };
}

function compareTriple(value: unknown): ProbabilityTriple | null {
  if (!value || typeof value !== "object") return null;
  const raw = record(value);
  if (typeof raw.home !== "number" || typeof raw.draw !== "number" || typeof raw.away !== "number") {
    return null;
  }
  return probs(value);
}

function aiResearch(value: unknown): AIResearchData | null {
  if (!value || typeof value !== "object") return null;
  const raw = record(value);
  const status = string(raw.status);
  if (!status) return null;
  return {
    status,
    headline: string(raw.headline),
    points: array(raw.points).map((x) => string(x)).filter(Boolean),
    sources: array(raw.sources).map((x) => {
      const item = record(x);
      return {
        name: nullableString(item.name) ?? undefined,
        fixture_id: typeof item.fixture_id === "number" ? item.fixture_id : undefined,
      };
    }),
    capturedAt: nullableString(raw.captured_at),
    expiresAt: nullableString(raw.expires_at),
  };
}

function probabilityCompare(value: unknown): ProbabilityCompareData | null {
  if (!value || typeof value !== "object") return null;
  const raw = record(value);
  const marketRaw = record(raw.market);
  const marketProbs = compareTriple(marketRaw.probs);
  const thirdRaw = record(raw.third_party ?? raw.thirdParty);
  const thirdProbs = compareTriple(thirdRaw.probs);
  return {
    sp: compareTriple(raw.sp),
    model: compareTriple(raw.model),
    market: marketProbs && typeof marketRaw.bookmaker === "string"
      ? { bookmaker: marketRaw.bookmaker, probs: marketProbs }
      : null,
    thirdParty: thirdProbs && typeof thirdRaw.source === "string"
      ? { source: thirdRaw.source, probs: thirdProbs,
          capturedAt: nullableString(thirdRaw.captured_at ?? thirdRaw.capturedAt) }
      : null,
    modelEnabled: Boolean(raw.model_enabled ?? raw.modelEnabled),
    modelStatus: nullableString(raw.model_status ?? raw.modelStatus),
    reason: nullableString(raw.reason),
    dataCutoff: nullableString(raw.data_cutoff ?? raw.dataCutoff),
  };
}

function odds(value: unknown) {
  const raw = record(value);
  return { h: number(raw.h, 0), d: number(raw.d, 0), a: number(raw.a, 0) };
}

function pick(value: unknown): VerdictPick | null {
  if (!value || typeof value !== "object") return null;
  const raw = record(value);
  return {
    dir: nullableString(raw.dir),
    label: nullableString(raw.label),
    sp: nullableNumber(raw.sp),
    prob: nullableNumber(raw.prob),
    ev: nullableNumber(raw.ev),
    goalLine: nullableString(raw.goal_line ?? raw.goalLine),
  };
}

export function adaptVerdictSummary(value: unknown): VerdictSummary | null {
  const raw = record(value);
  const payload = record(raw.payload);
  const id = string(raw.id);
  // 列表接口顶层有 match_id；详情接口把它放在 payload.match_id 里。
  const matchId = string(raw.match_id ?? raw.matchId ?? payload.match_id);
  if (!id || !matchId) return null;
  const modelRaw = record(raw.model);
  return {
    id,
    matchId,
    matchNo: string(raw.match_no ?? raw.matchNo),
    league: string(raw.league),
    home: string(raw.home),
    away: string(raw.away),
    kickoff: string(raw.kickoff),
    pool: string(raw.pool, "hhad"),
    goalLine: nullableString(raw.goal_line ?? raw.goalLine),
    sp: odds(raw.sp),
    rake: nullableNumber(raw.rake),
    rakeThreshold: nullableNumber(raw.rake_threshold ?? raw.rakeThreshold ?? payload.rake_threshold),
    probs: probs(raw.probs),
    model:
      Object.keys(modelRaw).length > 0
        ? {
            shrunk: Array.isArray(modelRaw.shrunk)
              ? modelRaw.shrunk.map((v) => number(v))
              : null,
            pick: modelRaw.pick,
            engine: nullableString(modelRaw.engine),
          }
        : null,
    pick: pick(raw.pick),
    status: string(raw.status, "screening"),
    tier: nullableString(raw.tier) ?? undefined,
    modelStatus: nullableString(raw.model_status ?? raw.modelStatus) ?? undefined,
    modelSource: nullableString(raw.model_source ?? raw.modelSource) ?? undefined,
    dataQuality: Object.keys(record(raw.data_quality ?? raw.dataQuality)).length > 0
      ? record(raw.data_quality ?? raw.dataQuality) : undefined,
    gates: gateMap(raw.gates),
    hash: nullableString(raw.hash ?? raw.payload_hash),
    sealed: boolean(raw.sealed, Boolean(raw.payload_hash)),
  };
}

function adaptYou(value: unknown): YouState | null {
  const raw = record(value);
  if (!string(raw.user_id)) return null;
  return {
    userId: string(raw.user_id),
    rested: boolean(raw.rested),
    restedUntil: string(raw.rested_until),
    protectionActive: boolean(raw.protection_active),
    streak: number(raw.streak),
    disciplineOn: boolean(raw.discipline_on, true),
  };
}

function adaptRest(value: unknown): RestDay | null {
  const raw = record(value);
  if (Object.keys(raw).length === 0) return null;
  const course = record(raw.course);
  return {
    message: string(raw.message),
    course: {
      id: string(course.id),
      title: string(course.title),
      minutes: number(course.minutes, 2),
      body: string(course.body),
    },
  };
}

export function adaptStream(value: unknown): StreamResponse {
  const raw = record(value);
  const statsRaw = record(raw.stats);
  const items = array(raw.verdicts)
    .map(adaptVerdictSummary)
    .filter((v): v is VerdictSummary => v !== null);
  return {
    tradeDate: string(raw.trade_date),
    mode: string(raw.mode, "normal"),
    generatedAt: string(raw.generated_at),
    stats: {
      total: number(statsRaw.total),
      priceFail: number(statsRaw.price_fail),
      pricePass: number(statsRaw.price_pass),
      promoted: number(statsRaw.promoted),
      screening: number(statsRaw.screening),
      gateNote: string(statsRaw.gate_note),
    },
    verdicts: items,
    nextCursor: nullableString(raw.next_cursor),
    watch: array(raw.watch)
      .map(adaptVerdictSummary)
      .filter((v): v is VerdictSummary => v !== null),
    avoid: array(raw.avoid).map((entry): AvoidItem => {
      const item = record(entry);
      return {
        matchId: string(item.match_id),
        matchNo: string(item.match_no),
        home: string(item.home),
        away: string(item.away),
        rake: number(item.rake),
        gate: string(item.gate, "price"),
        why: string(item.why),
        verdictId: string(item.verdict_id),
      };
    }),
    onsale: array(raw.onsale).map((entry): OnSaleItem => {
      const item = record(entry);
      return {
        matchId: string(item.match_id),
        matchNo: string(item.match_no),
        league: string(item.league),
        home: string(item.home),
        away: string(item.away),
        kickoff: string(item.kickoff),
        saleClose: string(item.sale_close ?? item.kickoff),
        single: boolean(item.single),
        rake: nullableNumber(item.rake),
        gates: item.gates ? gateMap(item.gates) : null,
        status: nullableString(item.status),
        tier: nullableString(item.tier),
        modelStatus: nullableString(item.model_status ?? item.modelStatus),
        verdictId: nullableString(item.verdict_id),
        coverage: item.coverage ? adaptCoverage(item.coverage) : null,
      };
    }),
    postmortems: array(raw.postmortems).map(adaptPostmortem),
    unattended: array(raw.unattended).map(adaptPostmortem),
    restDay: adaptRest(raw.rest_day),
    you: adaptYou(raw.you),
  };
}

export function adaptEvidence(value: unknown): EvidenceItem[] {
  return array(value).map((entry) => {
    const item = record(entry);
    return {
      tag: string(item.tag, "仅背景"),
      title: string(item.t ?? item.title ?? "判断依据"),
      detail: string(item.d ?? item.detail),
      source: string(item.src ?? item.source, "未标注来源"),
    };
  });
}

export function adaptVerdictDetail(value: unknown): VerdictDetail | null {
  const base = adaptVerdictSummary(value);
  if (!base) return null;
  const raw = record(value);
  const payload = record(raw.payload);
  return {
    ...base,
    tradeDate: string(raw.trade_date),
    probabilityCompare: probabilityCompare(raw.probability_compare ?? payload.probability_compare),
    aiResearch: aiResearch(raw.ai_research),
    gatesDetail: gateDetails(raw.gates),
    evidence: adaptEvidence(payload.evidence),
    dataCutoff: string(payload.data_cutoff ?? raw.data_cutoff),
    generatedAt: string(payload.generated_at ?? raw.generated_at),
    engine: string(payload.engine ?? raw.engine),
    sealedAt: utcIso(nullableString(raw.sealed_at)),
    createdAt: utcIso(string(raw.created_at)) ?? "",
    payloadHash: string(raw.payload_hash, base.hash ?? ""),
    payload: Object.keys(payload).length > 0 ? payload : null,
  };
}

export function adaptSeal(value: unknown): SealResponse {
  const raw = record(value);
  const chain = record(raw.chain);
  return {
    id: string(raw.id),
    algorithm: string(raw.algorithm, "sha256(canonical_json)"),
    canonicalForm: string(raw.canonical_form),
    payload: record(raw.payload),
    recomputedHash: string(raw.recomputed_hash),
    storedHash: string(raw.stored_hash),
    match: boolean(raw.match),
    revisionCount: number(raw.revision_count),
    revisions: array(raw.revisions).map((entry) => {
      const item = record(entry);
      return {
        hash: string(item.hash),
        dataCutoff: string(item.data_cutoff),
        chainHash: string(item.chain_hash),
        sealedAt: string(item.sealed_at),
      };
    }),
    chain: {
      prev: string(chain.prev),
      hash: string(chain.hash),
      verify: string(chain.verify, "/chain/verify"),
    },
    verifyHint: string(raw.verify_hint),
  };
}

export function adaptWhyNot(value: unknown): WhyNotResponse {
  const raw = record(value);
  const audit = record(raw.audit);
  const detail = record(raw.detail);
  return {
    status: string(raw.status),
    verdictId: nullableString(raw.verdict_id),
    matchNo: string(raw.match_no),
    league: string(raw.league),
    home: string(raw.home),
    away: string(raw.away),
    deadGate:
      raw.dead_gate === "price" || raw.dead_gate === "market" || raw.dead_gate === "model"
        ? raw.dead_gate
        : null,
    verdictKind:
      raw.verdict_kind === "fail" || raw.verdict_kind === "pending"
        ? raw.verdict_kind
        : null,
    title: string(raw.title),
    gates: record(raw.gates),
    detail,
    whatIf: string(raw.whatif),
    modelRuns: array(audit.model_runs).map((entry) => {
      const item = record(entry);
      return {
        gate: string(item.gate),
        result: string(item.result),
        detail: record(item.detail),
      };
    }),
    verdictHash: nullableString(audit.verdict_hash),
  };
}

export function adaptOnSale(value: unknown): OnSaleItem[] {
  const raw = record(value);
  return array(raw.matches).map((entry) => {
    const item = record(entry);
    return {
      matchId: string(item.match_id),
      matchNo: string(item.match_no),
      league: string(item.league),
      home: string(item.home),
      away: string(item.away),
      kickoff: string(item.kickoff),
      saleClose: string(item.sale_close ?? item.kickoff),
      single: boolean(item.single),
      rake: nullableNumber(item.rake),
      gates: item.gates ? gateMap(item.gates) : null,
      status: nullableString(item.status),
      tier: nullableString(item.tier),
      modelStatus: nullableString(item.model_status ?? item.modelStatus),
      verdictId: nullableString(item.verdict_id),
      coverage: item.coverage ? adaptCoverage(item.coverage) : null,
    };
  });
}

function adaptCoverage(value: unknown): OnSaleItem["coverage"] {
  const raw = record(value);
  return {
    score: Number(raw.score ?? 0),
    level: string(raw.level ?? "unknown"),
    deepEligible: Boolean(raw.deep_eligible),
    missing: stringArray(raw.missing),
  };
}

export function adaptStringList(value: unknown): string[] {
  return stringArray(value);
}

function adaptPostmortem(entry: unknown): PostmortemSummary {
  const item = record(entry);
  return {
    verdictId: string(item.verdict_id),
    matchNo: string(item.match_no),
    match: string(item.match),
    tradeDate: string(item.trade_date),
    settled: item.settled === "win" || item.settled === "lose" ? item.settled : null,
    resultScore: nullableString(item.result_score),
    attribution: nullableString(item.attribution),
    note: string(item.note),
    viewedAt: nullableString(item.viewed_at),
  };
}
