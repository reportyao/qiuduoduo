import { useEffect, useMemo, useState } from "react";
import { Linking, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SettingsPage } from "@/components/SettingsPage";
import {
  Button,
  Card,
  Chip,
  ErrorState,
  Field,
  SettingsGroup,
  SettingsRow,
  Skeleton,
  Stepper,
  Text,
  Toggle,
  useToast,
} from "@/components/ui";
import {
  useNotifySettingsQuery,
  useUpdateNotifyMutation,
} from "@/features/inbox/queries";
import type { NotifySettings } from "@/domain/types";
import { errorText } from "@/lib/errors";
import { colors, spacing } from "@/theme/tokens";

const EVENT_OPTIONS = [
  { id: "verdict_change", label: "结论变化" },
  { id: "verdict_promoted", label: "过三关" },
  { id: "close_soon", label: "停售提醒" },
  { id: "final", label: "终场" },
  { id: "settled", label: "结算" },
  { id: "daily_brief", label: "每日简报" },
];

const ALL_TYPES = EVENT_OPTIONS.map((option) => option.id);

export default function NotificationsScreen() {
  const router = useRouter();
  const toast = useToast();
  const query = useNotifySettingsQuery();
  const update = useUpdateNotifyMutation();
  const [draft, setDraft] = useState<NotifySettings | null>(null);

  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);

  const selectedTypes = useMemo(() => {
    if (!draft) return [];
    return draft.eventTypes.length === 0 ? ALL_TYPES : draft.eventTypes;
  }, [draft]);

  const setTypes = (types: string[]) => {
    if (!draft) return;
    setDraft({ ...draft, eventTypes: types.length === ALL_TYPES.length ? [] : types });
  };

  const save = async () => {
    if (!draft) return;
    if (!/^\d{2}:\d{2}$/.test(draft.quietStart) || !/^\d{2}:\d{2}$/.test(draft.quietEnd)) {
      toast.show("静默时段格式需要 HH:MM", "warning");
      return;
    }
    try {
      await update.mutateAsync({
        ...draft,
        channels: draft.channels.length > 0 ? draft.channels : ["inapp"],
      });
      toast.show("通知设置已保存", "success");
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  return (
    <SettingsPage title="通知设置" subtitle="只推你关心的" onBack={() => router.back()}>
      {query.isLoading || !draft ? (
        <View style={{ gap: spacing.sm }}>
          <Skeleton height={120} radius={18} />
          <Skeleton height={160} radius={18} />
        </View>
      ) : query.isError ? (
        <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
      ) : (
        <>
          <Card style={styles.notice}>
            <Text variant="smallStrong">通知里不会出现队名、赔率和“买”字</Text>
            <Text variant="caption" color={colors.muted} style={styles.note}>
              站内信可以写清楚比赛；锁屏推送只提醒「你关注的比赛有更新」。每日主动推送上限默认 2 条。
            </Text>
            <Button
              label="打开系统通知设置"
              variant="ghost"
              size="sm"
              icon="settings-outline"
              onPress={() => Linking.openSettings()}
            />
          </Card>

          <SettingsGroup title="渠道">
            <SettingsRow
              title="站内信"
              subtitle="始终可用，不受系统权限影响"
              right={
                <Toggle
                  value={draft.channels.includes("inapp")}
                  onChange={(next) => {
                    const channels = next
                      ? Array.from(new Set([...draft.channels, "inapp"]))
                      : draft.channels.filter((c) => c !== "inapp");
                    setDraft({ ...draft, channels: channels.length ? channels : ["inapp"] });
                  }}
                  label="站内信"
                />
              }
            />
            <SettingsRow
              title="推送"
              subtitle="Android 厂商通道接入后生效"
              right={
                <Toggle
                  value={draft.channels.includes("push")}
                  onChange={(next) => {
                    const channels = next
                      ? Array.from(new Set([...draft.channels, "push"]))
                      : draft.channels.filter((c) => c !== "push");
                    setDraft({ ...draft, channels });
                  }}
                  label="推送"
                />
              }
              last
            />
          </SettingsGroup>

          <Text variant="overline" color={colors.green}>推什么</Text>
          <View style={styles.chips}>
            {EVENT_OPTIONS.map((option) => {
              const selected = selectedTypes.includes(option.id);
              return (
                <Chip
                  key={option.id}
                  label={option.label}
                  selected={selected}
                  onPress={() =>
                    setTypes(
                      selected
                        ? selectedTypes.filter((id) => id !== option.id)
                        : [...selectedTypes, option.id],
                    )
                  }
                />
              );
            })}
          </View>

          <SettingsGroup title="频率">
            <SettingsRow
              title="暂停所有主动推送"
              subtitle="站内信仍会保留"
              right={
                <Toggle
                  value={draft.paused}
                  onChange={(paused) => setDraft({ ...draft, paused })}
                  label="暂停推送"
                />
              }
              last
            />
          </SettingsGroup>

          <Card style={styles.cap}>
            <Text variant="smallStrong">每日主动推送上限</Text>
            <Text variant="caption" color={colors.muted}>0 = 只留站内信；最多 10 条。</Text>
            <Stepper
              value={draft.dailyCap}
              onChange={(dailyCap) => setDraft({ ...draft, dailyCap })}
              min={0}
              max={10}
              step={1}
              suffix="条"
            />
          </Card>

          <View style={styles.quiet}>
            <View style={styles.flex}>
              <Field
                label="静默开始"
                value={draft.quietStart}
                onChangeText={(quietStart) => setDraft({ ...draft, quietStart })}
                keyboardType="numbers-and-punctuation"
                placeholder="23:30"
              />
            </View>
            <View style={styles.flex}>
              <Field
                label="静默结束"
                value={draft.quietEnd}
                onChangeText={(quietEnd) => setDraft({ ...draft, quietEnd })}
                keyboardType="numbers-and-punctuation"
                placeholder="08:00"
              />
            </View>
          </View>

          <Button label="保存设置" onPress={save} loading={update.isPending} fullWidth />
          <Text variant="caption" color={colors.subtle} center style={styles.note}>
            被你忽略的推送会自动降频。任何一条推送都可以在通知设置里一键关闭。
          </Text>
        </>
      )}
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  notice: { gap: spacing.xs },
  note: { lineHeight: 18 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  cap: { gap: spacing.xs },
  quiet: { flexDirection: "row", gap: spacing.sm },
  flex: { flex: 1 },
});
