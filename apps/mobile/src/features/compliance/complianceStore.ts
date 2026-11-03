import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";

const STORAGE_KEY = "jieqiu.compliance.v1";
const PERMANENT_UNTIL = 4102444800000; // 2100-01-01

export type ExclusionChoice = 7 | 30 | "permanent";

interface PersistedCompliance {
  excludedUntil: number | null;
  excludedAt: number | null;
  excludedPermanent: boolean;
  lastPgsiScore: number | null;
  lastPgsiAt: number | null;
}

interface ComplianceState extends PersistedCompliance {
  hydrated: boolean;
  hydrate: () => Promise<void>;
  exclude: (choice: ExclusionChoice) => void;
  setPgsi: (score: number) => void;
}

const DEFAULTS: PersistedCompliance = {
  excludedUntil: null,
  excludedAt: null,
  excludedPermanent: false,
  lastPgsiScore: null,
  lastPgsiAt: null,
};

function persist(state: ComplianceState): void {
  void AsyncStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      excludedUntil: state.excludedUntil,
      excludedAt: state.excludedAt,
      excludedPermanent: state.excludedPermanent,
      lastPgsiScore: state.lastPgsiScore,
      lastPgsiAt: state.lastPgsiAt,
    }),
  ).catch(() => {});
}

export const useComplianceStore = create<ComplianceState>((set, get) => ({
  ...DEFAULTS,
  hydrated: false,

  hydrate: async () => {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<PersistedCompliance>;
        set({
          excludedUntil: typeof parsed.excludedUntil === "number" ? parsed.excludedUntil : null,
          excludedAt: typeof parsed.excludedAt === "number" ? parsed.excludedAt : null,
          excludedPermanent: Boolean(parsed.excludedPermanent),
          lastPgsiScore:
            typeof parsed.lastPgsiScore === "number" ? parsed.lastPgsiScore : null,
          lastPgsiAt: typeof parsed.lastPgsiAt === "number" ? parsed.lastPgsiAt : null,
        });
      }
    } catch {
      // 读取失败不能把已有的自排除静默清掉；保持默认但标记 hydrated，
      // 服务端同步/重新进入页面时会再次校验。
    } finally {
      set({ hydrated: true });
    }
  },

  exclude: (choice) => {
    const now = Date.now();
    const until =
      choice === "permanent" ? PERMANENT_UNTIL : now + choice * 24 * 60 * 60 * 1000;
    set({
      excludedUntil: until,
      excludedAt: now,
      excludedPermanent: choice === "permanent",
    });
    persist(get());
  },

  setPgsi: (score) => {
    set({ lastPgsiScore: score, lastPgsiAt: Date.now() });
    persist(get());
  },
}));

export function isExcluded(until: number | null, now = Date.now()): boolean {
  return until != null && until > now;
}

/**
 * 自排除为「本机强制拦截」：后端合规接口尚未上线，因此在服务端同步之前，
 * 本机必须真实拦住首页/记录/记注，而不是只改一个开关。多设备同步列为上线前阻塞项。
 */
export function useExcluded(): boolean {
  const until = useComplianceStore((s) => s.excludedUntil);
  const permanent = useComplianceStore((s) => s.excludedPermanent);
  return permanent || isExcluded(until);
}
