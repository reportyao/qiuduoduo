import { StyleSheet, Text, View } from "react-native";
import { useHealthQuery } from "@/features/health/queries";

export default function HomeScreen() {
  const health = useHealthQuery();

  return (
    <View style={styles.screen}>
      <Text style={styles.brand}>解球</Text>
      <Text style={styles.subtitle}>AI 竞彩分析助理</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>引擎状态</Text>
        {health.isLoading ? (
          <Text style={styles.cardBody}>正在连接引擎…</Text>
        ) : health.isError ? (
          <Text style={[styles.cardBody, styles.error]}>
            暂时无法连接引擎，稍后自动重试。
          </Text>
        ) : (
          <Text style={styles.cardBody}>
            已连接 · 引擎正常
          </Text>
        )}
      </View>

      <Text style={styles.footnote}>
        生产界面迁移中。当前版本用于验证移动端架构与后端契约。
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F5F4EF",
    paddingHorizontal: 18,
    paddingTop: 18,
  },
  brand: {
    fontSize: 24,
    fontWeight: "600",
    color: "#15211B",
    letterSpacing: -0.5,
  },
  subtitle: {
    marginTop: 4,
    fontSize: 12,
    color: "#6B756F",
  },
  card: {
    marginTop: 18,
    padding: 16,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E9E7E0",
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0E6B4F",
  },
  cardBody: {
    marginTop: 8,
    fontSize: 13,
    lineHeight: 20,
    color: "#15211B",
  },
  error: {
    color: "#A8443A",
  },
  footnote: {
    marginTop: 16,
    fontSize: 11,
    lineHeight: 18,
    color: "#9AA69F",
  },
});
