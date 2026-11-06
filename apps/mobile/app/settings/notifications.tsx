import { useEffect, useMemo, useRef, useState } from "react";
import { goBackOr } from "@/lib/navigation";
import { Linking, Platform, StyleSheet, View } from "react-native";
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
  usePushHealthQuery,
  useUpdateNotifyMutation,
} from "@/features/inbox/queries";
import type { NotifySettings } from "@/domain/types";
import { requestNotificationPermission } from "@/features/push/jpush";
import { errorText } from "@/lib/errors";
import { colors, spacing } from "@/theme/tokens";

const EVENT_OPTIONS = [
  { id: "verdict_change", label: "预测更新" },
  { id: "verdict_promoted", label: "新预测" },
  { id: "close_soon", label: "停售提醒" },
  { id: "final", label: "终场" },
  { id: "settled", label: "结算" },
  { id: "daily_brief", label: "每日简报" },
];

const ALL_TYPES = EVENT_OPTIONS.map((option) => option.id);
// 后端约定空数组 = 全部；用哨兵表达“明确一个都不要”，避免取消最后一个类型后又变回全选。
const NONE_TYPE = "__none__";
const HM = /^([01]\d|2[0-3]):[0-5]\d$/;

export default function NotificationsScreen() {
  const router = useRouter();
  const toast = useToast();
  const query = useNotifySettingsQuery();
  const update = useUpdateNotifyMutation();
  const pushHealth = usePushHealthQuery();
  const [draft, setDraft] = useState<NotifySettings | null>(null);
  const dirty = useRef(false);

  useEffect(() => {
    if (query.data && !dirty.current) setDraft(query.data);
  }, [query.data]);

  const updateDraft = (next: NotifySettings) => {
    dirty.current = true;
    setDraft(next);
  };

  const selectedTypes = useMemo(() => {
    if (!draft) return [];
    if (draft.eventTypes.includes(NONE_TYPE)) return [];
    return draft.eventTypes.length === 0 ? ALL_TYPES : draft.eventTypes;
  }, [draft]);

  const setTypes = (types: string[]) => {
    if (!draft) return;
    const next =
      types.length === 0 ? [NONE_TYPE]
        : types.length === ALL_TYPES.length ? [] : types;
    updateDraft({ ...draft, eventTypes: next });
  };

  const save = async () => {
    if (!draft) return;
    if (!HM.test(draft.quietStart) || !HM.test(draft.quietEnd)) {
      toast.show("静默时段需要在 00:00–23:59 之间", "warning");
      return;
    }
    try {
      const saved = await update.mutateAsync({
        ...draft,
        channels: draft.channels.length > 0 ? draft.channels : ["inapp"],
      });
      dirty.current = false;
      setDraft(saved);
      toast.show("通知设置已保存", "success");
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  return (
    <SettingsPage title="通知设置" subtitle="只推你关心的" onBack={() => goBackOr(router)}>
      {query.isError && !draft ? (
        <ErrorState message={errorText(query.error)} onRetry={() => query.refetch()} />
      ) : query.isLoading || !draft ? (
        <View style={{ gap: spacing.sm }}>
          <Skeleton height={120} radius={18} />
          <Skeleton height={160} radius={18} />
        </View>
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
                    updateDraft({ ...draft, channels: channels.length ? channels : ["inapp"] });
                  }}
                  label="站内信"
                />
              }
            />
            <SettingsRow
              title="推送"
              subtitle="JPush 已接入；厂商通道待配置"
              right={
                <Toggle
                  value={draft.channels.includes("push")}
                  onChange={async (next) => {
                    if (next) {
                      const granted = await requestNotificationPermission();
                      if (!granted) {
                        toast.show("系统通知权限未开启，推送不会显示", "warning");
                      }
                    }
                    const channels = next
                      ? Array.from(new Set([...draft.channels, "push"]))
                      : draft.channels.filter((c) => c !== "push");
                    updateDraft({ ...draft, channels });
                  }}
                  label="推送"
                />
              }
            />
            {Platform.OS === "android" ? (
              <SettingsRow
                title="设备推送"
                subtitle={
                  pushHealth.isError
                    ? "状态待同步"
                    : pushHealth.data?.dryrun
                      ? "服务端推送待配置"
                      : "JPush 已配置"
                }
                value={
                  pushHealth.isLoading
                    ? "检查中"
                    : pushHealth.data && pushHealth.data.totalTokens > 0
                      ? `已绑定 ${pushHealth.data.totalTokens} 台`
                      : "等待注册"
                }
                icon="phone-portrait-outline"
                last
              />
            ) : null}
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
                  selectedStyle="soft"
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
                  onChange={(paused) => updateDraft({ ...draft, paused })}
                  label="暂停推送"
                />
              }
              last
            />
          </SettingsGroup>

          <Card style={styles.cap}>
            <Text variant="smallStrong">每日主动推送上限</Text>
            <Text variant="caption" color={colors.muted}>0 = 只留站内信；最多 10 条</Text>
            <Stepper
              value={draft.dailyCap}
              onChange={(dailyCap) => updateDraft({ ...draft, dailyCap })}
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
                onChangeText={(quietStart) => updateDraft({ ...draft, quietStart })}
                keyboardType="numbers-and-punctuation"
                placeholder="23:30"
              />
            </View>
            <View style={styles.flex}>
              <Field
                label="静默结束"
                value={draft.quietEnd}
                onChangeText={(quietEnd) => updateDraft({ ...draft, quietEnd })}
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
