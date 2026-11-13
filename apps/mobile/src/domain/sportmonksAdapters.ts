import { array, nullableNumber, number, numberRecord, record, string } from "@/lib/parse";
import { utcIso } from "@/lib/format";
import type {
  SportmonksH2HItem,
  SportmonksIntelData,
  SportmonksLineupPlayer,
  SportmonksLineupSide,
  SportmonksMarketBoard,
  SportmonksPredictionHighlight,
  SportmonksStandingRow,
} from "./types";

function lineupPlayer(value: unknown): SportmonksLineupPlayer | null {
  const raw = record(value);
  const name = string(raw.name);
  if (!name) return null;
  return {
    playerId: nullableNumber(raw.player_id ?? raw.playerId),
    name,
    number: nullableNumber(raw.number),
    position: string(raw.position),
    formationField: string(raw.formation_field ?? raw.formationField),
  };
}

function lineupSide(value: unknown): SportmonksLineupSide | null {
  const raw = record(value);
  const starters = array(raw.starters).map(lineupPlayer).filter(
    (item): item is SportmonksLineupPlayer => Boolean(item),
  );
  if (starters.length === 0) return null;
  return {
    teamId: nullableNumber(raw.team_id ?? raw.teamId),
    teamName: string(raw.team_name ?? raw.teamName),
    formation: string(raw.formation),
    starters,
    subs: array(raw.subs).map(lineupPlayer).filter(
      (item): item is SportmonksLineupPlayer => Boolean(item),
    ),
  };
}

function standingRow(value: unknown): SportmonksStandingRow | null {
  const raw = record(value);
  if (Object.keys(raw).length === 0) return null;
  return {
    position: nullableNumber(raw.position),
    points: nullableNumber(raw.points),
    played: nullableNumber(raw.played),
    won: nullableNumber(raw.won),
    drawn: nullableNumber(raw.drawn),
    lost: nullableNumber(raw.lost),
    goalsFor: nullableNumber(raw.goals_for ?? raw.goalsFor),
    goalsAgainst: nullableNumber(raw.goals_against ?? raw.goalsAgainst),
    goalDiff: nullableNumber(raw.goal_diff ?? raw.goalDiff),
    form: array(raw.form).map((item) => string(item)).filter(Boolean),
  };
}

function h2hItem(value: unknown): SportmonksH2HItem | null {
  const raw = record(value);
  const home = string(raw.home);
  const away = string(raw.away);
  const scoreHome = nullableNumber(raw.score_home ?? raw.scoreHome);
  const scoreAway = nullableNumber(raw.score_away ?? raw.scoreAway);
  if (!home || !away || scoreHome == null || scoreAway == null) return null;
  return {
    date: string(raw.date),
    home,
    away,
    scoreHome,
    scoreAway,
    result: string(raw.result),
    league: string(raw.league),
  };
}

function highlight(value: unknown): SportmonksPredictionHighlight | null {
  const raw = record(value);
  const key = string(raw.key);
  const label = string(raw.label);
  if (!key) return null;
  const scores = array(raw.scores).map((entry) => {
    const item = record(entry);
    return {
      score: string(item.score),
      probability: nullableNumber(item.probability),
    };
  }).filter((item) => Boolean(item.score));
  return {
    key,
    label,
    values: Object.keys(record(raw.values)).length > 0
      ? numberRecord(raw.values)
      : undefined,
    scores: scores.length > 0 ? scores : undefined,
  };
}

function market(value: unknown): SportmonksMarketBoard | null {
  const raw = record(value);
  const key = string(raw.key);
  if (!key) return null;
  const selections = array(raw.selections).map((entry) => {
    const item = record(entry);
    return {
      label: string(item.label),
      price: nullableNumber(item.price),
      probability: nullableNumber(item.probability),
    };
  }).filter((item) => Boolean(item.label));
  if (selections.length === 0) return null;
  return {
    key,
    name: string(raw.name),
    bookmaker: string(raw.bookmaker),
    line: string(raw.line),
    selections,
  };
}

/** Sportmonks 结构化情报适配；缺字段返回 null，不编造。 */
export function adaptSportmonksIntel(value: unknown): SportmonksIntelData | null {
  const raw = record(value);
  if (Object.keys(raw).length === 0) return null;
  const lineups = record(raw.lineups);
  const standings = record(raw.standings);
  const venue = record(raw.venue);
  const weather = record(raw.weather);
  const coaches = record(raw.coaches);
  const referees = record(raw.referees);
  const mainRef = record(referees.main);
  const recent = record(raw.recent);
  return {
    fixtureId: nullableNumber(raw.fixture_id ?? raw.fixtureId),
    league: string(raw.league),
    venue: Object.keys(venue).length > 0 ? {
      name: string(venue.name),
      city: string(venue.city),
      capacity: nullableNumber(venue.capacity),
      surface: string(venue.surface),
    } : null,
    weather: Object.keys(weather).length > 0 ? {
      description: string(weather.description),
      temperature: numberRecord(weather.temperature),
      feelsLike: numberRecord(weather.feels_like ?? weather.feelsLike),
      wind: numberRecord(weather.wind),
      humidity: string(weather.humidity),
      clouds: string(weather.clouds),
    } : null,
    coaches: {
      home: record(coaches.home).name ? { name: string(record(coaches.home).name) } : undefined,
      away: record(coaches.away).name ? { name: string(record(coaches.away).name) } : undefined,
    },
    referees: {
      main: mainRef.name ? { name: string(mainRef.name), role: string(mainRef.role) } : undefined,
      crewCount: number(referees.crew_count ?? referees.crewCount),
    },
    formations: {
      home: string(record(raw.formations).home),
      away: string(record(raw.formations).away),
    },
    lineups: {
      home: lineupSide(lineups.home) ?? undefined,
      away: lineupSide(lineups.away) ?? undefined,
    },
    sidelined: array(raw.sidelined).map((entry) => {
      const item = record(entry);
      return {
        playerName: string(item.player_name ?? item.playerName),
        side: string(item.side),
        typeLabel: string(item.type_label ?? item.typeLabel),
      };
    }).filter((item) => Boolean(item.playerName)),
    standings: {
      home: standingRow(standings.home) ?? undefined,
      away: standingRow(standings.away) ?? undefined,
    },
    h2h: array(raw.h2h).map(h2hItem).filter(
      (item): item is SportmonksH2HItem => Boolean(item),
    ),
    recent: {
      home: array(recent.home).map((item) => string(item)).filter(Boolean),
      away: array(recent.away).map((item) => string(item)).filter(Boolean),
    },
    predictionHighlights: array(
      Array.isArray(raw.prediction_highlights ?? raw.predictionHighlights)
        ? raw.prediction_highlights ?? raw.predictionHighlights
        : record(raw.prediction_highlights ?? raw.predictionHighlights).items,
    )
      .map(highlight)
      .filter((item): item is SportmonksPredictionHighlight => Boolean(item)),
    marketBoard: array(raw.market_board ?? raw.marketBoard)
      .map(market)
      .filter((item): item is SportmonksMarketBoard => Boolean(item)),
    matchFacts: array(raw.match_facts ?? raw.matchFacts).map((entry) => {
      const item = record(entry);
      return {
        typeName: string(item.type_name ?? item.typeName),
        text: string(item.text),
      };
    }).filter((item) => Boolean(item.text)),
    expectedLineups: number(raw.expected_lineups ?? raw.expectedLineups),
    prematchNews: array(raw.prematch_news ?? raw.prematchNews).map((entry) => {
      const item = record(entry);
      return { title: string(item.title), text: string(item.text) };
    }).filter((item) => Boolean(item.title || item.text)),
    postmatch: (() => {
      const item = record(raw.postmatch);
      if (Object.keys(item).length === 0) return null;
      return {
        scoreHome: nullableNumber(item.score_home ?? item.scoreHome),
        scoreAway: nullableNumber(item.score_away ?? item.scoreAway),
        xgHome: nullableNumber(item.xg_home ?? item.xgHome),
        xgAway: nullableNumber(item.xg_away ?? item.xgAway),
        goals: array(item.goals).map((entry) => {
          const goal = record(entry);
          return {
            minute: nullableNumber(goal.minute),
            player: string(goal.player),
            side: string(goal.side),
            result: string(goal.result),
          };
        }).filter((goal) => Boolean(goal.player)),
        capturedAt: utcIso(string(item.captured_at ?? item.capturedAt)),
      };
    })(),
    sections: Object.fromEntries(
      Object.entries(record(raw.section_meta ?? raw.sectionMeta)).map(([key, value]) => {
        const item = record(value);
        return [key, {
          capturedAt: utcIso(string(item.captured_at ?? item.capturedAt)),
          ttlSeconds: nullableNumber(item.ttl_seconds ?? item.ttlSeconds),
        }];
      }),
    ),
    capturedAt: utcIso(string(raw.data_cutoff ?? raw.captured_at ?? raw.capturedAt)),
  };
}
