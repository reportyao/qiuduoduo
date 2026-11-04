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
  storageError: boolean;
  hydrate: () => Promise<void>;
  exclude: (choice: ExclusionChoice) => Promise<boolean>;
  setPgsi: (score: number) => void;
  clearPgsi: () => void;
}

const DEFAULTS: PersistedCompliance = {
  excludedUntil: null,
  excludedAt: null,
  excludedPermanent: false,
  lastPgsiScore: null,
  lastPgsiAt: null,
};

function serialize(state: PersistedCompliance): string {
  return JSON.stringify({
    excludedUntil: state.excludedUntil,
    excludedAt: state.excludedAt,
    excludedPermanent: state.excludedPermanent,
    lastPgsiScore: state.lastPgsiScore,
    lastPgsiAt: state.lastPgsiAt,
  });
}

function persist(state: ComplianceState): void {
  void AsyncStorage.setItem(STORAGE_KEY, serialize(state)).catch(() => {});
}

export const useComplianceStore = create<ComplianceState>((set, get) => ({
  ...DEFAULTS,
  hydrated: false,
  storageError: false,

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
          storageError: false,
        });
      }
    } catch {
      // 读取失败时不能宣称“未排除”；标记错误，由入口提示重试（fail closed）。
      set({ storageError: true });
    } finally {
      set({ hydrated: true });
    }
  },

  exclude: async (choice) => {
    const now = Date.now();
    const until =
      choice === "permanent" ? PERMANENT_UNTIL : now + choice * 24 * 60 * 60 * 1000;
    const next = {
      excludedUntil: until,
      excludedAt: now,
      excludedPermanent: choice === "permanent",
    };
    try {
      // 先持久化再宣布成功：写失败时绝不显示“已生效”。
      await AsyncStorage.setItem(STORAGE_KEY, serialize({ ...get(), ...next }));
      set({ ...next, storageError: false });
      return true;
    } catch {
      set({ storageError: true });
      return false;
    }
  },

  setPgsi: (score) => {
    set({ lastPgsiScore: score, lastPgsiAt: Date.now() });
    persist(get());
  },

  clearPgsi: () => {
    set({ lastPgsiScore: null, lastPgsiAt: null });
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
