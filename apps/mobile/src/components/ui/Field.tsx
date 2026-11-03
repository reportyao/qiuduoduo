import { useState } from "react";
import {
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { colors, fontFamily, layout, radii, spacing, type } from "@/theme/tokens";
import { Text } from "./Text";

interface FieldProps extends TextInputProps {
  label?: string;
  hint?: string;
  error?: string | null;
  right?: React.ReactNode;
  containerStyle?: StyleProp<ViewStyle>;
}

export function Field({ label, hint, error, right, containerStyle, style, ...rest }: FieldProps) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={[styles.wrap, containerStyle]}>
      {label ? <Text variant="captionStrong" color={colors.muted}>{label}</Text> : null}
      <View
        style={[
          styles.field,
          focused && styles.focused,
          error ? styles.errorBorder : null,
        ]}
      >
        <TextInput
          {...rest}
          accessibilityLabel={label}
          onFocus={(e) => {
            setFocused(true);
            rest.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            rest.onBlur?.(e);
          }}
          placeholderTextColor={colors.subtle}
          style={[styles.input, style]}
          selectionColor={colors.green}
        />
        {right}
      </View>
      {error ? (
        <Text variant="caption" color={colors.danger}>{error}</Text>
      ) : hint ? (
        <Text variant="caption" color={colors.muted}>{hint}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.xs },
  field: {
    minHeight: layout.inputHeight,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bgElevated,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  focused: { borderColor: colors.green, backgroundColor: colors.surface },
  errorBorder: { borderColor: colors.danger },
  input: {
    flex: 1,
    paddingVertical: spacing.base,
    color: colors.ink,
    fontFamily: fontFamily.regular,
    fontSize: type.body.fontSize,
    lineHeight: type.body.lineHeight,
  },
});
