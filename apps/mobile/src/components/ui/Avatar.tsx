import { useEffect, useState } from "react";
import { Image, StyleSheet, View, type ImageSourcePropType } from "react-native";
import { colors, shadows } from "@/theme/tokens";

interface AvatarProps {
  source: ImageSourcePropType;
  size?: number;
  ring?: boolean;
  /** 透明底：悬浮头像只保留角色本身，不要白色圆盘/阴影。 */
  bare?: boolean;
  online?: boolean;
  fallbackSource?: ImageSourcePropType;
}

export function Avatar({
  source,
  size = 56,
  ring = true,
  bare = false,
  online = false,
  fallbackSource,
}: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const sourceKey =
    typeof source === "object" && source !== null && "uri" in source
      ? String(source.uri)
      : String(source);

  useEffect(() => {
    setFailed(false);
  }, [sourceKey]);
  return (
    <View style={{ width: size, height: size }}>
      <View
        style={[
          styles.badge,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderWidth: ring ? 2 : 0,
          },
          bare && styles.bare,
        ]}
      >
        <Image
          source={failed && fallbackSource ? fallbackSource : source}
          style={{ width: size - 4, height: size - 4 }}
          resizeMode="cover"
          onError={() => setFailed(true)}
        />
      </View>
      {online ? (
        <View
          style={[
            styles.online,
            { width: size * 0.22, height: size * 0.22, borderRadius: size * 0.11 },
          ]}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: colors.white,
    borderColor: colors.white,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    ...shadows.card,
  },
  bare: {
    backgroundColor: "transparent",
    borderColor: "transparent",
    shadowOpacity: 0,
    elevation: 0,
  },
  online: {
    position: "absolute",
    right: 2,
    bottom: 4,
    backgroundColor: colors.green,
    borderWidth: 2,
    borderColor: colors.white,
  },
});
