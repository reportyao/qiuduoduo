import React from "react";
import { View, StyleSheet } from "react-native";
import { Button, Text } from "@/components/ui";
import { colors, layout, spacing } from "@/theme/tokens";

interface State {
  hasError: boolean;
}

/**
 * 全局错误边界：任何子组件 render 抛异常时，显示友好错误而非白屏。
 * 用户可点击重启清除错误状态，恢复到正常渲染。
 */
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (__DEV__) {
      console.error("[ErrorBoundary]", error, info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.screen}>
          <Text variant="h3">出了点问题</Text>
          <Text variant="small" color={colors.muted} style={styles.body}>
            应用遇到了一个意外错误。点击重启返回首页。
          </Text>
          <Button
            label="重启"
            variant="primary"
            onPress={() => this.setState({ hasError: false })}
            style={styles.button}
          />
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.bg,
    paddingHorizontal: layout.pagePadding,
    gap: spacing.md,
  },
  body: { textAlign: "center", lineHeight: 20 },
  button: { minWidth: 160, marginTop: spacing.sm },
});
