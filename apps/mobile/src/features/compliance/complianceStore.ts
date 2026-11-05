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
  /** 本机已生效但服务端尚未确认；联网/登录后必须重试，否则换设备可绕过。 */
  syncPending: boolean;
}

interface ComplianceState extends PersistedCompliance {
  hydrated: boolean;
  storageError: boolean;
  hydrate: () => Promise<void>;
  exclude: (choice: ExclusionChoice) => Promise<boolean>;
  markSynced: () => void;
  setPgsi: (score: number) => void;
  clearPgsi: () => void;
  applyServerState: (state: {
    excludedUntil: number | null;
    excludedAt: number | null;
    excludedPermanent: boolean;
    pgsiScore: number | null;
    pgsiAt: number | null;
  }) => void;
}

const DEFAULTS: PersistedCompliance = {
  excludedUntil: null,
  excludedAt: null,
  excludedPermanent: false,
  lastPgsiScore: null,
  lastPgsiAt: null,
  syncPending: false,
};

function serialize(state: PersistedCompliance): string {
  return JSON.stringify({
    excludedUntil: state.excludedUntil,
    excludedAt: state.excludedAt,
    excludedPermanent: state.excludedPermanent,
    lastPgsiScore: state.lastPgsiScore,
    lastPgsiAt: state.lastPgsiAt,
    syncPending: state.syncPending,
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
          syncPending: Boolean(parsed.syncPending),
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
      syncPending: true,
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

  markSynced: () => {
    set({ syncPending: false });
    persist(get());
  },

  setPgsi: (score) => {
    set({ lastPgsiScore: score, lastPgsiAt: Date.now() });
    persist(get());
  },

  clearPgsi: () => {
    set({ lastPgsiScore: null, lastPgsiAt: null });
    persist(get());
  },

  applyServerState: (state) => {
    set({
      excludedUntil: state.excludedUntil,
      excludedAt: state.excludedAt,
      excludedPermanent: state.excludedPermanent,
      lastPgsiScore: state.pgsiScore,
      lastPgsiAt: state.pgsiAt,
      syncPending: false,
      storageError: false,
    });
    persist(get());
  },
}));

export function isExcluded(until: number | null, now = Date.now()): boolean {
  return until != null && until > now;
}

/**
 * 自排除：本机立即强制拦截；登录后 useComplianceSync 用服务端状态覆盖本机，
 * 服务端 /bets 与 focus.capabilities 同步硬拦截，重装/换设备不能绕过。
 */
export function useExcluded(): boolean {
  const until = useComplianceStore((s) => s.excludedUntil);
  const permanent = useComplianceStore((s) => s.excludedPermanent);
  return permanent || isExcluded(until);
}
