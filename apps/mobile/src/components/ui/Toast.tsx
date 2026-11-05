import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Animated, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, radii, shadows, spacing } from "@/theme/tokens";
import { Text } from "./Text";
import { Icon, type IconName } from "./Icon";

type ToastKind = "success" | "info" | "warning" | "error";

interface ToastState {
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  show: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const KIND_META: Record<ToastKind, { icon: IconName; color: string; bg: string }> = {
  success: { icon: "checkmark-circle", color: colors.greenAccent, bg: "rgba(14,107,79,0.94)" },
  info: { icon: "information-circle", color: colors.white, bg: "rgba(21,33,27,0.94)" },
  warning: { icon: "alert-circle", color: "#FFD99B", bg: "rgba(90,58,14,0.96)" },
  error: { icon: "close-circle", color: "#FFD3CC", bg: "rgba(125,42,34,0.96)" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  const [toast, setToast] = useState<ToastState | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const translate = useRef(new Animated.Value(10)).current;
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastId = useRef(0);

  const hide = useCallback(() => {
    const id = toastId.current;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 160, useNativeDriver: true }),
      Animated.timing(translate, { toValue: 10, duration: 160, useNativeDriver: true }),
    ]).start(() => {
      // 旧 toast 的淡出回调不能清掉淡出期间新 show 的 toast。
      if (toastId.current === id) setToast(null);
    });
  }, [opacity, translate]);

  const show = useCallback(
    (message: string, kind: ToastKind = "info") => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      toastId.current += 1;
      setToast({ message, kind });
      opacity.setValue(0);
      translate.setValue(10);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }),
        Animated.timing(translate, { toValue: 0, duration: 180, useNativeDriver: true }),
      ]).start();
      hideTimer.current = setTimeout(hide, 1800);
    },
    [hide, opacity, translate],
  );

  useEffect(() => {
    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, []);

  const value = useMemo(() => ({ show }), [show]);
  const meta = toast ? KIND_META[toast.kind] : KIND_META.info;

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast ? (
        <Animated.View
          pointerEvents="none"
          accessibilityLiveRegion="polite"
          style={[
            styles.wrap,
            {
              bottom: insets.bottom + 86,
              opacity,
              transform: [{ translateY: translate }],
            },
          ]}
        >
          <View style={[styles.toast, { backgroundColor: meta.bg }]}>
            <Icon name={meta.icon} size={17} color={meta.color} />
            <Text variant="smallStrong" color={colors.white} style={styles.text}>
              {toast.message}
            </Text>
          </View>
        </Animated.View>
      ) : null}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast 必须在 ToastProvider 内使用");
  }
  return ctx;
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: spacing.xxl,
    right: spacing.xxl,
    alignItems: "center",
    zIndex: 999,
  },
  toast: {
    maxWidth: 420,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.base,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    ...shadows.float,
  },
  text: { flexShrink: 1 },
});
