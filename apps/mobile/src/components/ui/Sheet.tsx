import { useEffect, type ReactNode } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useFloatingStore } from "@/features/assistant/floatingStore";
import { colors, layout, radii, spacing } from "@/theme/tokens";
import { IconButton } from "./IconButton";
import { Text } from "./Text";

interface SheetProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  scrollable?: boolean;
  closeLabel?: string;
}

/**
 * 底部弹层：所有购买、筛选、封存、分享都复用它。
 * 点击遮罩 / Android 返回键关闭；键盘弹出时上移，不遮挡金额输入。
 */
export function Sheet({
  visible,
  onClose,
  title,
  subtitle,
  children,
  footer,
  scrollable = true,
  closeLabel = "关闭",
}: SheetProps) {
  const insets = useSafeAreaInsets();
  const pushSheet = useFloatingStore((s) => s.pushSheet);
  const popSheet = useFloatingStore((s) => s.popSheet);

  // 原生 Modal 会盖住整个 Tab 层，但悬浮头像在 Modal 之上；
  // 打开期间把头像收掉，避免它悬在遮罩上方挡内容。
  useEffect(() => {
    if (!visible) return;
    pushSheet();
    return popSheet;
  }, [visible, pushSheet, popSheet]);

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      statusBarTranslucent
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.fill}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${closeLabel}弹层背景`}
          style={styles.backdrop}
          onPress={onClose}
        />
        <View style={[styles.panel, { paddingBottom: Math.max(insets.bottom, spacing.base) }]}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <View style={styles.headerText}>
              <Text variant="h3">{title}</Text>
              {subtitle ? (
                <Text variant="caption" color={colors.muted} style={styles.subtitle}>
                  {subtitle}
                </Text>
              ) : null}
            </View>
            <IconButton name="close" onPress={onClose} accessibilityLabel={closeLabel} size={18} />
          </View>
          {scrollable ? (
            <ScrollView
              style={styles.body}
              contentContainerStyle={styles.bodyContent}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >
              {children}
            </ScrollView>
          ) : (
            <View style={styles.bodyContent}>{children}</View>
          )}
          {footer ? <View style={styles.footer}>{footer}</View> : null}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, justifyContent: "flex-end" },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.overlay },
  panel: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.sheet,
    borderTopRightRadius: radii.sheet,
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
    maxHeight: "86%",
  },
  handle: {
    alignSelf: "center",
    width: 38,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.lineStrong,
    marginBottom: spacing.base,
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.base,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1, gap: 2 },
  subtitle: { lineHeight: 17 },
  body: { flexGrow: 0 },
  bodyContent: { paddingVertical: spacing.sm },
  footer: { paddingTop: spacing.base, gap: spacing.sm },
});
