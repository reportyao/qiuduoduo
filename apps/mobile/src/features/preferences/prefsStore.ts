import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { normalizePersona, type PersonaId } from "@/features/personas/personaIds";

export type OddsFormat = "decimal" | "hk" | "indo" | "american";
export type AgeDecision = "unknown" | "adult" | "minor";

const STORAGE_KEY = "jieqiu.prefs.v1";

interface PersistedPrefs {
  persona: PersonaId;
  oddsFormat: OddsFormat;
  ageDecision: AgeDecision;
  notificationPromptDismissed: boolean;
  avatarUri: string | null;
  lastDailyRecordDate: string;
}

interface PrefsState extends PersistedPrefs {
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setPersona: (persona: PersonaId) => void;
  setOddsFormat: (format: OddsFormat) => void;
  setAvatarUri: (uri: string | null) => void;
  setAgeDecision: (decision: AgeDecision) => void;
  dismissNotificationPrompt: () => void;
  setLastDailyRecordDate: (date: string) => void;
}

const DEFAULTS: PersistedPrefs = {
  persona: "zhuanjia",
  oddsFormat: "decimal",
  ageDecision: "unknown",
  notificationPromptDismissed: false,
  avatarUri: null,
  lastDailyRecordDate: "",
};

function isOddsFormat(value: unknown): value is OddsFormat {
  return value === "decimal" || value === "hk" || value === "indo" || value === "american";
}

function snapshot(state: PrefsState): PersistedPrefs {
  return {
    persona: state.persona,
    oddsFormat: state.oddsFormat,
    ageDecision: state.ageDecision,
    notificationPromptDismissed: state.notificationPromptDismissed,
    avatarUri: state.avatarUri,
    lastDailyRecordDate: state.lastDailyRecordDate,
  };
}

function persist(state: PrefsState): void {
  void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot(state))).catch(() => {
    // 偏好写入失败不阻塞交互；下次启动回落到默认值。
  });
}

export const usePrefsStore = create<PrefsState>((set, get) => ({
  ...DEFAULTS,
  hydrated: false,

  hydrate: async () => {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (!raw) {
        set({ hydrated: true });
        return;
      }
      const parsed = JSON.parse(raw) as Partial<PersistedPrefs>;
      set({
        persona: normalizePersona(parsed.persona),
        oddsFormat: isOddsFormat(parsed.oddsFormat) ? parsed.oddsFormat : "decimal",
        ageDecision:
          parsed.ageDecision === "adult" || parsed.ageDecision === "minor"
            ? parsed.ageDecision
            : "unknown",
        notificationPromptDismissed: Boolean(parsed.notificationPromptDismissed),
        avatarUri: typeof parsed.avatarUri === "string" ? parsed.avatarUri : null,
        lastDailyRecordDate: typeof parsed.lastDailyRecordDate === "string"
          ? parsed.lastDailyRecordDate : "",
        hydrated: true,
      });
    } catch {
      set({ hydrated: true });
    }
  },

  setPersona: (persona) => {
    set({ persona });
    persist(get());
  },

  setOddsFormat: (oddsFormat) => {
    set({ oddsFormat });
    persist(get());
  },

  setAvatarUri: (avatarUri) => {
    set({ avatarUri });
    persist(get());
  },

  setAgeDecision: (ageDecision) => {
    set({ ageDecision });
    persist(get());
  },

  dismissNotificationPrompt: () => {
    set({ notificationPromptDismissed: true });
    persist(get());
  },

  setLastDailyRecordDate: (lastDailyRecordDate) => {
    set({ lastDailyRecordDate });
    persist(get());
  },
}));

export function usePersonaId(): PersonaId {
  return usePrefsStore((s) => s.persona);
}

export function useOddsFormat(): OddsFormat {
  return usePrefsStore((s) => s.oddsFormat);
}
