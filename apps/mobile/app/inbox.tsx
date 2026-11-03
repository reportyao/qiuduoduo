import { useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import { Button, Card, Chip, EmptyState, ErrorState, Skeleton, StatusDot, Text, useToast } from "@/components/ui";
import { useInboxMutations, useInboxQuery } from "@/features/inbox/queries";
import { errorText } from "@/lib/errors";
import { relativeTime, todayCn } from "@/lib/format";
import { colors, layout, radii, spacing } from "@/theme/tokens";
import type { InboxItem } from "@/domain/types";

export default function InboxScreen() {
  const router = useRouter();
  const toast = useToast();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const query = useInboxQuery(unreadOnly);
  const { markRead, readAll, click } = useInboxMutations();
  const inbox = query.data;
  const items = useMemo(() => inbox?.items ?? [], [inbox]);

  const open = async (item: InboxItem) => {
    try {
      if (!item.openedAt) await markRead.mutateAsync(item.id);
      const result = await click.mutateAsync(item.id);
      const link = result.deeplink || item.deepLink;
      routeDeepLink(link, router);
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="收件箱"
        subtitle={inbox ? `${inbox.unread} 条未读` : "站内信与提醒"}
        showAssistant={false}
        onBack={() => router.back()}
        right={
          (inbox?.unread ?? 0) > 0 ? (
            <Button
              label="全部已读"
              variant="ghost"
              size="sm"
              onPress={() => readAll.mutate()}
              loading={readAll.isPending}
            />
          ) : null
        }
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={query.isRefetching} onRefresh={() => query.refetch()} tintColor={colors.green} />
        }
      >
        <View style={styles.filters}>
          <Chip label="全部" selected={!unreadOnly} onPress={() => setUnreadOnly(false)} />
          <Chip label="仅未读" selected={unreadOnly} onPress={() => setUnreadOnly(true)} />
        </View>

        {query.isLoading ? (
          <View style={{ gap: spacing.sm }}>
            <Skeleton height={80} radius={16} />
            <Skeleton height={80} radius={16} />
          </View>
        ) : query.isError ? (
          <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            icon="notifications-outline"
            title={unreadOnly ? "没有未读消息" : "收件箱是空的"}
            body="关注比赛后，结论变化、停售和终场提醒会出现在这里。站内信不受系统通知权限影响。"
            actionLabel="去关注比赛"
            onAction={() => router.push("/watch")}
          />
        ) : (
          <View style={styles.list}>
            {items.map((item) => (
              <Pressable
                key={item.id}
                onPress={() => void open(item)}
                accessibilityRole="button"
                accessibilityLabel={`${item.title}${item.openedAt ? "" : "，未读"}`}
                style={({ pressed }) => [styles.row, !item.openedAt && styles.unread, pressed && styles.pressed]}
              >
                <View style={styles.dotCol}>
                  {!item.openedAt ? <StatusDot color={colors.green} size={7} /> : null}
                </View>
                <View style={styles.flex}>
                  <Text variant={item.openedAt ? "bodyStrong" : "bodyStrong"}>{item.title}</Text>
                  <Text variant="small" color={colors.muted} style={styles.body} numberOfLines={2}>
                    {item.body}
                  </Text>
                  <Text variant="caption" color={colors.subtle}>{relativeTime(item.createdAt)}</Text>
                </View>
                <Text variant="caption" color={colors.green}>查看</Text>
              </Pressable>
            ))}
          </View>
        )}

        <Card tone="green" style={styles.note}>
          <Text variant="caption" color={colors.muted} style={styles.noteText}>
            系统推送只写「你关注的比赛有更新」，不写队名、赔率和“买”字。站内信才会展开具体内容。
          </Text>
        </Card>
      </ScrollView>
    </AppScreen>
  );
}

function routeDeepLink(
  link: string | null,
  router: ReturnType<typeof useRouter>,
): void {
  if (!link) return;
  const verdict = link.match(/jieqiu:\/\/verdict\/([^/?#]+)/);
  if (verdict) {
    router.push({ pathname: "/verdict/[id]", params: { id: verdict[1] } });
    return;
  }
  const match = link.match(/jieqiu:\/\/match\/([^/?#]+)/);
  if (match) {
    router.push({ pathname: "/match/[id]", params: { id: match[1], date: todayCn() } });
    return;
  }
  if (link.startsWith("jieqiu://today")) router.push("/(tabs)");
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.sm, paddingBottom: spacing.x7 },
  filters: { flexDirection: "row", gap: spacing.xs, marginBottom: spacing.sm },
  list: { backgroundColor: colors.surface, borderRadius: radii.card, borderWidth: 1, borderColor: colors.line, overflow: "hidden" },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
    padding: spacing.base,
    paddingHorizontal: spacing.xl,
    minHeight: 92,
  },
  unread: { backgroundColor: colors.greenSoft },
  pressed: { opacity: 0.75 },
  dotCol: { width: 8, paddingTop: 6 },
  flex: { flex: 1, gap: 3 },
  body: { lineHeight: 19 },
  note: { marginTop: spacing.base },
  noteText: { lineHeight: 18 },
});
