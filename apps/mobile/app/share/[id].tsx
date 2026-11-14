import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ScrollView, StyleSheet, View } from "react-native";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Card, ErrorState, Icon, KeyValueRow, Skeleton, Text } from "@/components/ui";
import { api } from "@/lib/api";
import { callApi } from "@/lib/callApi";
import { errorText } from "@/lib/errors";
import { record, string } from "@/lib/parse";
import { formatDateTime, shortHash } from "@/lib/format";
import { colors, layout, spacing } from "@/theme/tokens";

/**
 * 分享卡落地页（jieqiu://share/{id}）。
 * 分享内容本身由服务端按规范化 JSON 重新哈希；这里只展示验真结果与原文。
 */
export default function ShareScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const query = useQuery({
    queryKey: ["share", id],
    queryFn: async () => {
      const raw = await callApi(
        api.client.GET("/share/{share_id}", { params: { path: { share_id: id! } } }),
      );
      return record(raw);
    },
    enabled: Boolean(id),
    retry: false,
  });

  const data = query.data;
  const match = Boolean(data?.match);
  const payload = record(data?.payload);

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="分享卡验真"
        subtitle="编号 = 哈希前 12 位"
        showAssistant={false}
        onBack={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))}
      />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {query.isLoading ? (
          <>
            <Skeleton height={120} radius={20} />
            <Skeleton height={220} radius={20} style={{ marginTop: spacing.base }} />
          </>
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : data ? (
          <>
            <Card tone={match ? "positive" : "negative"} style={styles.verify}>
              <Icon
                name={match ? "shield-checkmark" : "alert-circle"}
                size={26}
                color={match ? colors.brand : colors.loss}
              />
              <View style={styles.flex}>
                <Text variant="h3" color={match ? colors.brand : colors.loss}>
                  {match ? "分享卡有效 · 内容一致" : "分享卡校验失败"}
                </Text>
                <Text variant="caption" color={colors.muted}>
                  编号 {string(data.share_id)} · {string(data.kind, "share")}
                </Text>
              </View>
            </Card>

            <Card style={styles.block}>
              <KeyValueRow label="分享编号" value={string(data.share_id)} />
              <KeyValueRow label="内容哈希" value={shortHash(string(data.content_hash), 12, 10)} />
              <KeyValueRow label="复算哈希" value={shortHash(string(data.recomputed_hash), 12, 10)} />
              <KeyValueRow label="算法" value={string(data.algorithm, "sha256(canonical_json)")} last />
            </Card>

            <Card style={styles.block}>
              <Text variant="overline" color={colors.brand}>分享原文</Text>
              <Text variant="mono" color={colors.muted} selectable style={styles.payload}>
                {JSON.stringify(payload, null, 2)}
              </Text>
            </Card>

            {data.verdict_seal_url ? (
              <Card
                tone="positive"
                onPress={() => {
                  const parts = string(data.verdict_seal_url).split("/").filter(Boolean);
                  const idx = parts.indexOf("verdicts");
                  const verdictId = idx >= 0 ? parts[idx + 1] : undefined;
                  if (verdictId) router.push({ pathname: "/verdict/[id]", params: { id: verdictId } });
                }}
                accessibilityLabel="查看原判决封存"
                style={styles.link}
              >
                <Text variant="smallStrong" color={colors.brand}>查看原判决封存</Text>
                <Icon name="arrow-forward" size={15} color={colors.brand} />
              </Card>
            ) : null}
            {string(payload.data_cutoff) ? (
              <Text variant="caption" color={colors.subtle} center>
                数据截止 {formatDateTime(string(payload.data_cutoff))}
              </Text>
            ) : null}
          </>
        ) : null}
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.md, paddingBottom: spacing.x7 },
  flex: { flex: 1 },
  verify: { flexDirection: "row", alignItems: "center", gap: spacing.base },
  block: { marginTop: spacing.base, gap: spacing.xs },
  payload: { lineHeight: 17, fontSize: 11 },
  link: { marginTop: spacing.base, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
});
