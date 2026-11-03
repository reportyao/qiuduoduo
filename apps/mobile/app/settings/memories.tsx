import { useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Alert, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Skeleton,
  Text,
  useToast,
} from "@/components/ui";
import { useMeQuery, useMemoryMutations } from "@/features/account/queries";
import { ApiError, errorText } from "@/lib/errors";
import { colors, spacing } from "@/theme/tokens";

export default function MemoriesScreen() {
  const router = useRouter();
  const toast = useToast();
  const meQuery = useMeQuery();
  const { save, remove } = useMemoryMutations();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const memories = meQuery.data?.memories ?? [];

  const add = async (confirm = false) => {
    if (!key.trim() || !value.trim()) {
      toast.show("写清楚记什么，以及内容", "warning");
      return;
    }
    try {
      await save.mutateAsync({ key: key.trim(), value: value.trim(), confirm });
      setKey("");
      setValue("");
      toast.show("记住了", "success");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        Alert.alert(
          "已有不同的记忆",
          "绝不静默覆盖。要改成你现在说的这条吗？",
          [
            { text: "保留原来", style: "cancel" },
            { text: "确认覆盖", style: "destructive", onPress: () => void add(true) },
          ],
        );
        return;
      }
      toast.show(errorText(e), "error");
    }
  };

  const del = (name: string) => {
    Alert.alert("删除记忆", `确定不再记住「${name}」？`, [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            await remove.mutateAsync(name);
            toast.show("已删除", "info");
          } catch (e) {
            toast.show(errorText(e), "error");
          }
        },
      },
    ]);
  };

  return (
    <SettingsPage title="它记得你什么" subtitle="可见、可改、可删" onBack={() => goBackOr(router)}>
      <Card tone="green">
        <Text variant="small" color={colors.muted} style={styles.note}>
          记忆只用来调整助理的说话方式和偏好，不参与比赛概率计算，也不会出现在推送里。
        </Text>
      </Card>

      {meQuery.isLoading ? (
        <Skeleton height={80} radius={18} />
      ) : meQuery.isError ? (
        <ErrorState message={errorText(meQuery.error)} onRetry={() => meQuery.refetch()} />
      ) : memories.length === 0 ? (
        <EmptyState
          icon="bookmark-outline"
          title="还没有记住任何事"
          body="你可以在对话里说「记住我的主队是曼城」，也可以在这里手动添加。"
          actionLabel="去问助理"
          onAction={() => router.push("/assistant")}
        />
      ) : (
        <View style={styles.list}>
          {memories.map((memory) => (
            <Card key={memory.key} style={styles.memory}>
              <View style={styles.flex}>
                <Text variant="bodyStrong">{memory.key}</Text>
                <Text variant="small" color={colors.muted}>{memory.value}</Text>
                <Text variant="caption" color={colors.subtle}>来源：{memory.source}</Text>
              </View>
              <Button label="删除" variant="ghost" size="sm" onPress={() => del(memory.key)} />
            </Card>
          ))}
        </View>
      )}

      <Card style={styles.add}>
        <Text variant="h3">手动添加</Text>
        <Field label="记什么" value={key} onChangeText={setKey} placeholder="例如：主队偏好" maxLength={64} />
        <Field label="内容" value={value} onChangeText={setValue} placeholder="例如：曼城" maxLength={200} />
        <Button label="记住" variant="secondary" onPress={() => void add(false)} loading={save.isPending} fullWidth />
      </Card>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  note: { lineHeight: 19 },
  list: { gap: spacing.sm },
  memory: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  flex: { flex: 1, gap: 2 },
  add: { gap: spacing.sm },
});
