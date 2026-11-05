import type { PersonaId } from "@/features/personas/personas";
import type { OddsFormat } from "@/features/preferences/prefsStore";

export type GateKey = "price" | "market" | "model";
export type GateResult = "pass" | "fail" | "pending_data" | "unknown";
export type VerdictStatus = "promoted" | "screening" | "killed" | string;
export type Settlement = "win" | "lose" | null;

export interface OddsTriple {
  h: number;
  d: number;
  a: number;
}

export interface ProbabilityTriple {
  home: number;
  draw: number;
  away: number;
}

export interface VerdictPick {
  dir: string | null;
  label?: string | null;
  sp?: number | null;
  prob?: number | null;
  ev?: number | null;
  goalLine?: string | null;
}

export interface GateDetail {
  gate: GateKey;
  result: GateResult;
  detail: Record<string, unknown>;
}

export interface VerdictSummary {
  id: string;
  matchId: string;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  pool: string;
  goalLine: string | null;
  sp: OddsTriple;
  rake: number | null;
  rakeThreshold: number | null;
  probs: ProbabilityTriple;
  model: { shrunk?: number[] | null; pick?: unknown; engine?: string | null } | null;
  pick: VerdictPick | null;
  status: VerdictStatus;
  gates: Partial<Record<GateKey, GateResult>>;
  hash: string | null;
  sealed: boolean;
  snapshotId?: string;
  snapshotStatus?: string;
  direction?: string;
  confidence?: number | null;
  conditions?: string[];
  invalidators?: string[];
  review?: RecommendationReview | null;
}

export interface RecommendationReview {
  status: string;
  reviewer: string;
  reviewedAt: string | null;
  promptVer: string;
  llmDegraded: boolean;
  layers: Record<string, unknown>[];
}

export interface StreamStats {
  total: number;
  priceFail: number;
  pricePass: number;
  promoted: number;
  screening: number;
  gateNote: string;
}

export interface AvoidItem {
  matchId: string;
  matchNo: string;
  home: string;
  away: string;
  rake: number;
  gate: GateKey | string;
  why: string;
  verdictId: string;
}

export interface OnSaleCoverage {
  score: number;
  level: string;
  deepEligible: boolean;
  missing: string[];
}

export interface OnSaleItem {
  matchId: string;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  saleClose: string;
  single: boolean;
  rake: number | null;
  gates: Partial<Record<GateKey, GateResult>> | null;
  status: VerdictStatus | null;
  verdictId: string | null;
  coverage: OnSaleCoverage | null;
}

export interface RestDay {
  message: string;
  course: { id: string; title: string; minutes: number; body: string };
}

export interface YouState {
  userId: string;
  rested: boolean;
  restedUntil: string;
  protectionActive: boolean;
  streak: number;
  disciplineOn: boolean;
}

export interface PostmortemSummary {
  verdictId: string;
  matchNo: string;
  match: string;
  tradeDate: string;
  settled: Settlement;
  resultScore: string | null;
  attribution: string | null;
  note: string;
}

export interface StreamResponse {
  tradeDate: string;
  mode: "normal" | "rest_day" | string;
  generatedAt: string;
  stats: StreamStats;
  verdicts: VerdictSummary[];
  nextCursor: string | null;
  watch: VerdictSummary[];
  avoid: AvoidItem[];
  onsale: OnSaleItem[];
  postmortems: PostmortemSummary[];
  restDay: RestDay | null;
  you: YouState | null;
}

export interface EvidenceItem {
  tag: string;
  title: string;
  detail: string;
  source: string;
}

export interface VerificationRevision {
  hash: string;
  dataCutoff: string;
  chainHash: string;
  sealedAt: string;
}

export interface SealResponse {
  id: string;
  algorithm: string;
  canonicalForm: string;
  payload: Record<string, unknown>;
  recomputedHash: string;
  storedHash: string;
  match: boolean;
  revisionCount: number;
  revisions: VerificationRevision[];
  chain: { prev: string; hash: string; verify: string };
  verifyHint: string;
}

export interface VerdictDetail extends VerdictSummary {
  tradeDate: string;
  gatesDetail: Partial<Record<GateKey, GateDetail>>;
  evidence: EvidenceItem[];
  dataCutoff: string;
  generatedAt: string;
  engine: string;
  sealedAt: string | null;
  createdAt: string;
  payloadHash: string;
  payload: Record<string, unknown> | null;
}

export interface WhyNotResponse {
  status: VerdictStatus;
  verdictId: string | null;
  matchNo: string;
  league: string;
  home: string;
  away: string;
  deadGate: GateKey | null;
  verdictKind: "fail" | "pending" | null;
  title: string;
  gates: Record<string, unknown>;
  detail: Record<string, unknown>;
  whatIf: string;
  modelRuns: { gate: string; result: string; detail: Record<string, unknown> }[];
  verdictHash: string | null;
}

export interface IntelDimension {
  key: string;
  label: string;
  value: string;
  direction: "up" | "down" | "flat" | "unknown";
  note: string;
  source?: string;
}

export interface IntelReport {
  headline: string;
  summary: string;
  dimensions: IntelDimension[];
  unPriced: number;
  total: number;
  cutoff: string;
  sourceCount: number;
  isFallback: boolean;
}

export interface BetRecord {
  id: number;
  verdictId: string;
  match: string;
  matchNo: string;
  amount: number;
  pool: string;
  goalLine: string | null;
  sp: number | null;
  pickDir: string;
  status: VerdictStatus;
  settled: Settlement;
  resultScore: string | null;
  pnl: number | null;
}

export interface WeeklyReport {
  rangeDays: number;
  verdictsTotal: number;
  promoted: number;
  settled: number;
  wins: number;
  attribution: Record<string, number>;
  killed: {
    rangeDays: number;
    killedTotal: number;
    settled: number;
    wouldLose: number;
    wouldWin: number;
    avoidedLossCny: number;
    missedWinCny: number;
  };
  you: { bets: number; settledBets: number; pnl: number; attribution: Record<string, number> } | null;
}

export interface Postmortem {
  id: string;
  matchNo: string;
  match: string;
  tradeDate: string;
  pool: string;
  goalLine: string | null;
  pick: VerdictPick | null;
  status: VerdictStatus;
  settled: Settlement;
  resultScore: string | null;
  kind: string;
  deadGate?: GateKey | null;
  why?: Record<string, unknown>;
  whatIf: string;
  attribution?: { settled: boolean; class: string | null; note: string };
  bet?: { amount: number; pickDir: string; pnl: number | null; sp?: number | null };
}

export interface LedgerStats {
  promotedTotal: number;
  settled: number;
  wins: number;
  losses: number;
  currentLosingStreak: number;
}

export interface LedgerItem {
  id: string;
  tradeDate: string;
  matchNo: string;
  match: string;
  league: string;
  kickoff: string;
  pool: string;
  goalLine: string | null;
  pick: VerdictPick | null;
  status: VerdictStatus;
  settled: Settlement;
  resultScore: string | null;
  hash: string;
}

export interface LedgerResponse {
  items: LedgerItem[];
  stats: LedgerStats;
}

export interface MeProfile {
  userId: string;
  displayName: string;
  persona: PersonaId;
  oddsFormat: OddsFormat;
  locale: string;
  region: string;
  disciplineOn: boolean;
  phone: string | null;
  email: string | null;
  streak: {
    streak: number;
    active: boolean;
    threshold: number;
    rested: boolean;
    restedUntil: string;
    disciplineOn: boolean;
  };
  restedUntil: string;
  memories: { key: string; value: string; source: string }[];
}

export interface InboxItem {
  id: number;
  eventId: number | null;
  title: string;
  body: string;
  deepLink: string | null;
  createdAt: string;
  openedAt: string | null;
  clickedAt: string | null;
}

export interface InboxResponse {
  unread: number;
  items: InboxItem[];
}

export interface WatchItem {
  id: number;
  targetType: string;
  targetId: string;
  events: string[];
  matchNo: string | null;
  home: string | null;
  away: string | null;
  league: string | null;
  kickoff: string | null;
}

export interface NotifySettings {
  channels: string[];
  eventTypes: string[];
  quietStart: string;
  quietEnd: string;
  dailyCap: number;
  paused: boolean;
}

export interface ChatCard {
  type: string;
  text: string;
  verdictId?: string;
  deadGate?: string;
  memories?: { key: string; value: string; source: string }[];
  protection?: { streak: number; active: boolean };
  memory?: { key: string; value: string; status: string };
  conflict?: { key: string; existing: string; incoming: string };
  postmortem?: Postmortem;
}

export interface AuthProvider {
  id: string;
  label: string;
  primary?: boolean;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string | null;
  expiresAt: number | null;
  deviceToken: string | null;
  userId: string | null;
  mode: "device" | "jwt";
  displayName?: string | null;
}

export interface LegalText {
  region: string;
  helpline: string;
  compliance: string;
  minAge: number;
  dataSource: string;
}

export interface AppVersionInfo {
  api: string;
  minAppVersion: string;
  forceUpdateBelow: string;
  freezeMode: boolean;
}
