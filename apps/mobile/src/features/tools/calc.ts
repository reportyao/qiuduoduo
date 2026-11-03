export interface ParlayLeg {
  odds: number;
  rake: number;
  label?: string;
}

export interface ParlayResult {
  comboOdds: number;
  impliedProbability: number;
  theoreticalReturnRate: number;
  expectedReturn: number;
  expectedLoss: number;
  costPct: number;
  stake: number;
}

/**
 * 串关口径（可在页面附录复算）：
 * 组合赔率 = Π decimal_i
 * 组合隐含胜率 = 1 / 组合赔率
 * 理论返还率 = Π(1 - 单腿抽水)
 * 期望返还 = 本金 × 理论返还率
 * 期望损耗 = 本金 - 期望返还
 *
 * 这是“按市场概率”的数学期望，不代表真实命中率；真实胜率由模型给出。
 */
export function parlayMath(legs: ParlayLeg[], stake: number): ParlayResult {
  const comboOdds = legs.reduce((acc, leg) => acc * Math.max(leg.odds, 1.0001), 1);
  const theoreticalReturnRate = legs.reduce(
    (acc, leg) => acc * Math.max(0, 1 - leg.rake),
    1,
  );
  const expectedReturn = stake * theoreticalReturnRate;
  return {
    comboOdds,
    impliedProbability: comboOdds > 0 ? 1 / comboOdds : 0,
    theoreticalReturnRate,
    expectedReturn,
    expectedLoss: stake - expectedReturn,
    costPct: 1 - theoreticalReturnRate,
    stake,
  };
}

export interface RakeResult {
  overround: number;
  rake: number;
  returnRate: number;
  probs: [number, number, number];
  fairOdds: [number, number, number];
}

export function rakeMath(odds: [number, number, number]): RakeResult {
  const inv = odds.map((o) => (o > 1 ? 1 / o : 0)) as [number, number, number];
  const total = inv[0] + inv[1] + inv[2];
  const overround = total - 1;
  const rake = total > 0 ? overround / total : 0;
  return {
    overround,
    rake,
    returnRate: total > 0 ? 1 / total : 0,
    probs: total > 0 ? [inv[0] / total, inv[1] / total, inv[2] / total] : [0, 0, 0],
    fairOdds: total > 0 ? [total / inv[0] || 0, total / inv[1] || 0, total / inv[2] || 0] : [0, 0, 0],
  };
}

export interface OddsConversion {
  decimal: number;
  hk: number;
  indo: number;
  american: number;
  implied: number;
}

export function oddsMath(decimal: number): OddsConversion {
  const d = Math.max(decimal, 1.0001);
  return {
    decimal: d,
    hk: d - 1,
    indo: d >= 2 ? d - 1 : -1 / (d - 1),
    american: d >= 2 ? (d - 1) * 100 : -100 / (d - 1),
    implied: 1 / d,
  };
}

export interface KellyResult {
  edge: number;
  fullKelly: number;
  stake: number;
  capped: boolean;
}

/**
 * 凯利：f* = (b·p - q) / b，b = decimal - 1。
 * 页面默认半凯利，并强制 5% 本金上限（避免“全仓”误导）。
 */
export function kellyMath(input: {
  bankroll: number;
  probability: number;
  decimal: number;
  fraction?: number;
  cap?: number;
}): KellyResult {
  const b = Math.max(input.decimal - 1, 0.0001);
  const p = Math.min(Math.max(input.probability, 0), 1);
  const q = 1 - p;
  const edge = p * input.decimal - 1;
  const fullKelly = Math.max(0, (b * p - q) / b);
  const fraction = input.fraction ?? 0.5;
  const cap = input.cap ?? 0.05;
  const rawStake = input.bankroll * fullKelly * fraction;
  const maxStake = input.bankroll * cap;
  return {
    edge,
    fullKelly,
    stake: Math.min(rawStake, maxStake),
    capped: rawStake > maxStake,
  };
}

export interface BreakEvenResult {
  winRate: number;
  profit: number;
  loss: number;
  expectedValue: number;
  winsOfTen: number;
}

export function breakEvenMath(decimal: number, stake: number, probability?: number): BreakEvenResult {
  const d = Math.max(decimal, 1.0001);
  const winRate = 1 / d;
  const profit = stake * (d - 1);
  const loss = stake;
  const p = probability ?? winRate;
  return {
    winRate,
    profit,
    loss,
    expectedValue: p * profit - (1 - p) * loss,
    winsOfTen: winRate * 10,
  };
}

export function parseNumber(value: string): number | null {
  const normalized = value.replace(/[^\d.-]/g, "");
  if (!normalized) return null;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}
