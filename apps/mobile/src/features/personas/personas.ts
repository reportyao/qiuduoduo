import type { PersonaId } from "./personaIds";

export { PERSONA_ORDER, normalizePersona, type PersonaId } from "./personaIds";

export interface PersonaMeta {
  id: PersonaId;
  name: string;
  tag: string;
  address: string;
  sample: string;
  avatar: number;
}

/**
 * 人设只改变「语气」，绝不改变数字、结论、三关状态、合规提示。
 * 头像资源由 Metro 静态 require，新增人设时同时补 copy 与 avatar。
 */
export const PERSONAS: Record<PersonaId, PersonaMeta> = {
  zhuanjia: {
    id: "zhuanjia",
    name: "理性专家",
    tag: "冷静 · 简单直接",
    address: "你",
    sample: "让球主胜 54.2%。市场少算了两名中卫。",
    avatar: require("../../../assets/mascot/zhuanjia.png"),
  },
  laopao: {
    id: "laopao",
    name: "感性老炮",
    tag: "兄弟 · 幽默 · 有情绪",
    address: "兄弟",
    sample: "兄弟，这价我不拦你，但账得算明白。",
    avatar: require("../../../assets/mascot/laopao.png"),
  },
  meng: {
    id: "meng",
    name: "元气搭子",
    tag: "活泼 · 直白 · 不绕弯",
    address: "你",
    sample: "这场我算过啦，先听我说完嘛。",
    avatar: require("../../../assets/mascot/meng.png"),
  },
};

export interface PersonaCopy {
  brandSub: string;
  hintMatches: string;
  envLive: (total: number, promoted: number, screening: number) => string;
  envEmpty: string;
  saleTitle: string;
  parlayTitle: string;
  parlaySub: string;
  parlayCta: string;
  feedTitle: string;
  conversationOpen: (dayLabel: string, total: number, promoted: number, published: number, screening: number, killed: number) => string;
  typing: string;
  avoidLead: string;
  postmortemLead: string;
  buy: string;
  bought: string;
  detail: string;
  pendingCta: string;
  emptyTitle: string;
  emptyBody: string;
  pendingTitle: string;
  pendingBody: string;
  restTitle: string;
  restBody: string;
  comfort: string;
  protection: (streak: number) => string;
  chatPlaceholder: string;
  chatGreeting: string;
  whyNotLead: string;
  footer: string;
  verdictSummary: (args: {
    status: string;
    pickLabel: string;
    prob: number | null;
    rake: number | null;
    pendingGate: string | null;
    gateNote: string;
  }) => string;
}

export const COPY: Record<PersonaId, PersonaCopy> = {
  zhuanjia: {
    brandSub: "AI 赛前预测",
    hintMatches: "点我看今日全部比赛",
    envLive: (total, promoted, screening) =>
      `实时数据 · 已复核 ${total} 场 · 过三关 ${promoted} · 复核中 ${screening}`,
    envEmpty: "实时数据 · 正在同步今日场次",
    saleTitle: "最近停售",
    parlayTitle: "串关参谋 · 免费",
    parlaySub: "从预测生成组合，也可以自己体检",
    parlayCta: "去参谋",
    feedTitle: "今日预测",
    conversationOpen: (dayLabel, total, promoted, published, screening, killed) =>
      `${dayLabel} ${total} 场：复核过三关 ${promoted} 场，已发布预测 ${published} 场，${screening} 场等数据${killed ? `，${killed} 场没有预测` : ""}。没把握的，我不预测。`,
    typing: "正在生成预测…",
    avoidLead: "这几场我不给预测，原因都写在这：",
    postmortemLead: "最近几场预测复盘，输赢都写：",
    buy: "记一注",
    bought: "已记 ✓",
    detail: "看完整预测",
    pendingCta: "为什么不出预测",
    emptyTitle: "今晚没有值得发布的预测。",
    emptyBody: "没有把握就不发预测。你可以看今天在售、翻昨日复盘，或者看两分钟为什么。",
    pendingTitle: "今天的预测还没发布。",
    pendingBody: "引擎还没复核完今日场次。先去今日在售看赛程，或翻昨日复盘。",
    restTitle: "今天歇一天。",
    restBody: "歇一天不是放弃，是纪律的一部分。明天预测照常等你。",
    comfort: "记下了。中间不用再看了，有结果我会叫你。",
    protection: (streak) => `你已连败 ${streak} 场，保护已触发：今天先只看，不下。`,
    chatPlaceholder: "继续问球多多…",
    chatGreeting: "我在。问今日预测、问为什么不出、问复盘，或者让我记住你的偏好。",
    whyNotLead: "不出预测不是它不会赢，是我们算不清。算不清就不预测。",
    footer: "数据分析结果，不构成投注建议。未满 18 周岁禁止购买彩票。",
    verdictSummary: ({ status, pickLabel, prob, rake, pendingGate, gateNote }) => {
      if (status === "promoted") {
        return `预测 ${pickLabel}，概率 ${prob != null ? (prob * 100).toFixed(1) + "%" : "--"}。` +
          `官方定价抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}，三关已过。`;
      }
      if (status === "screening" && pendingGate) {
        return `价闸已过（抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}），` +
          `还在等「${pendingGate}」。${gateNote || "数据不齐，暂不发布预测。"}`;
      }
      return gateNote || "这场暂时没有预测，先看数据。";
    },
  },
  laopao: {
    brandSub: "AI 赛前预测 · 老炮坐镇",
    hintMatches: "点我，今天的场子都在这儿",
    envLive: (total, promoted, screening) =>
      `实时数据 · 盯完 ${total} 场 · 过三关 ${promoted} · 还在等 ${screening}`,
    envEmpty: "实时数据 · 正在把今天的场子扒一遍",
    saleTitle: "最近停售",
    parlayTitle: "串关参谋，免费",
    parlaySub: "把预测拆成组合，别让串关把账搅浑",
    parlayCta: "去参谋",
    feedTitle: "今日预测",
    conversationOpen: (dayLabel, total, promoted, published, screening, killed) =>
      `${dayLabel === "今天" ? "今儿" : dayLabel} ${total} 场，我扒了一遍：复核过三关 ${promoted} 场，已发布预测 ${published} 场，还有 ${screening} 场等数据${killed ? `，${killed} 场没给预测` : ""}。没把握的，老炮不瞎给预测。`,
    typing: "正在生成预测…",
    avoidLead: "这几场我不给预测，原因都在这：",
    postmortemLead: "最近几场预测，输赢都摆出来：",
    buy: "记一注",
    bought: "记上了 ✓",
    detail: "看完整预测",
    pendingCta: "为啥不出预测",
    emptyTitle: "兄弟，今晚没值得发的预测。",
    emptyBody: "不是没场，是没一场有把握。咱不硬凑，翻翻昨天，或者看今天在售。",
    pendingTitle: "兄弟，今天的预测还在路上。",
    pendingBody: "引擎还没把今天的场子跑完。先看今天在售，或者翻翻昨天。",
    restTitle: "兄弟，今晚收手。",
    restBody: "输钱不输阵。歇一晚，明天再预测。",
    comfort: "记上了兄弟。中间别刷了，有结果我叫你。",
    protection: (streak) => `兄弟，连输 ${streak} 场了，先停一停。低谷加注最容易把坑挖深。`,
    chatPlaceholder: "跟老炮聊聊…",
    chatGreeting: "来了兄弟。今天看哪场预测、为啥不出、昨天咋样，直接问。",
    whyNotLead: "不出预测不代表它不会赢。是这账咱算不清，算不清就不瞎给。",
    footer: "数据分析结果，不构成投注建议。未满 18 周岁禁止购买彩票。",
    verdictSummary: ({ status, pickLabel, prob, rake, pendingGate, gateNote }) => {
      if (status === "promoted") {
        return `兄弟，预测 ${pickLabel}，模型给到 ${prob != null ? (prob * 100).toFixed(1) + "%" : "--"}，` +
          `抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}，三关都过了。`;
      }
      if (status === "screening" && pendingGate) {
        return `价这关过了，抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}，` +
          `可「${pendingGate}」还没齐。急啥，等数据齐了再给预测。`;
      }
      return gateNote || "这场暂时没有预测，先看数据。";
    },
  },
  meng: {
    brandSub: "AI 赛前预测 · 陪你看方向",
    hintMatches: "点我，今日比赛都在这儿",
    envLive: (total, promoted, screening) =>
      `实时数据 · 我复核了 ${total} 场 · 过三关 ${promoted} · 复核中 ${screening}`,
    envEmpty: "实时数据 · 我正在同步今天的比赛",
    saleTitle: "最近停售啦",
    parlayTitle: "串关参谋 · 免费",
    parlaySub: "把预测拆成组合，我 30 秒算给你看",
    parlayCta: "去参谋",
    feedTitle: "今日预测",
    conversationOpen: (dayLabel, total, promoted, published, screening, killed) =>
      `${dayLabel} ${total} 场，我都看过啦：复核过三关 ${promoted} 场，已发布预测 ${published} 场，还有 ${screening} 场等数据${killed ? `，${killed} 场没给预测` : ""}。没把握的先不预测。`,
    typing: "我正在生成预测…",
    avoidLead: "这几场我不给预测，原因都写好啦：",
    postmortemLead: "最近几场预测复盘，输赢我都记着：",
    buy: "记一注",
    bought: "记好啦 ✓",
    detail: "看完整预测",
    pendingCta: "为什么不出预测呀",
    emptyTitle: "今晚没有值得发布的预测。",
    emptyBody: "场次都看完啦，没把握就不发预测。可以看看在售，或者翻昨日复盘。",
    pendingTitle: "今天的预测还没发布。",
    pendingBody: "今天的比赛还没跑完呢。先看在售，或者翻昨日复盘嘛。",
    restTitle: "今天休息嘛。",
    restBody: "歇一天不是放弃，是纪律的一部分。明天我照常给你预测。",
    comfort: "记下啦～中间不用看，有结果我第一时间来报。",
    protection: (streak) => `已经连输 ${streak} 场了，先停一停好不好？我不想看你越陷越深。`,
    chatPlaceholder: "想聊什么呀…",
    chatGreeting: "我在呢。今天看哪场预测、为什么不出、昨天怎么样，都可以问我。",
    whyNotLead: "不出预测不是它不会赢，是我算不清。算不清就不预测。",
    footer: "数据分析结果，不构成投注建议。未满 18 周岁禁止购买彩票。",
    verdictSummary: ({ status, pickLabel, prob, rake, pendingGate, gateNote }) => {
      if (status === "promoted") {
        return `预测 ${pickLabel}，概率 ${prob != null ? (prob * 100).toFixed(1) + "%" : "--"}，` +
          `抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}，三关都过啦。`;
      }
      if (status === "screening" && pendingGate) {
        return `价闸过啦，抽水 ${rake != null ? (rake * 100).toFixed(1) + "%" : "待同步"}，` +
          `可是「${pendingGate}」还没齐，等齐了再给预测嘛。`;
      }
      return gateNote || "这场暂时没有预测，先看数据嘛。";
    },
  },
};
