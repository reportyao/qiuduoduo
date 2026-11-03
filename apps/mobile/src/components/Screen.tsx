import type { ReactNode } from "react";
import {
  ScrollView,
  StyleSheet,
  type RefreshControlProps,
  type ScrollViewProps,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, layout, spacing } from "@/theme/tokens";

export function AppScreen({
  children,
  style,
  bottom = true,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  bottom?: boolean;
}) {
  return (
    <SafeAreaView
      edges={bottom ? ["left", "right", "bottom"] : ["left", "right"]}
      style={[styles.screen, style]}
    >
      {children}
    </SafeAreaView>
  );
}

interface ScrollPageProps extends ScrollViewProps {
  children: ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
  refreshControl?: React.ReactElement<RefreshControlProps>;
  extraBottom?: number;
}

/** 统一页面滚动容器：两侧 18px、底部避开 Tab/输入条。 */
export function ScrollPage({
  children,
  contentStyle,
  extraBottom = 0,
  ...rest
}: ScrollPageProps) {
  return (
    <ScrollView
      {...rest}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={[
        styles.content,
        { paddingBottom: 40 + layout.tabBarHeight + extraBottom },
        contentStyle,
      ]}
    >
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: {
    paddingHorizontal: layout.pagePadding,
    paddingTop: spacing.sm,
  },
});
