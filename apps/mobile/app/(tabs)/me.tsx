import { useState } from "react";
import { Alert, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { AppHeader } from "@/components/AppHeader";
import { AppScreen } from "@/components/Screen";
import {
  Avatar,
  Button,
  Card,
  Chip,
  ErrorState,
  Icon,
  IconButton,
  SettingsGroup,
  SettingsRow,
  Text,
  Toggle,
  useToast,
} from "@/components/ui";
import { usePersonaContent } from "@/features/personas/usePersona";
import { useAuthStore, isLoggedIn } from "@/features/auth/authStore";
import { useMeQuery, useDisciplineMutation, useRestMutation } from "@/features/account/queries";
import { useUnreadCountQuery } from "@/features/inbox/queries";
import { useOddsFormat, usePrefsStore } from "@/features/preferences/prefsStore";
import { errorText } from "@/lib/errors";
import { colors, layout, spacing } from "@/theme/tokens";

export default function MeScreen() {
  const router = useRouter();
  const toast = useToast();
  const { meta, copy } = usePersonaContent();
  const session = useAuthStore((s) => s.session);
  const logout = useAuthStore((s) => s.logout);
  const setPersona = usePrefsStore((s) => s.setPersona);
  const setOddsFormat = usePrefsStore((s) => s.setOddsFormat);
  const setAvatarUri = usePrefsStore((s) => s.setAvatarUri);
  const avatarUri = usePrefsStore((s) => s.avatarUri);
  const oddsFormat = useOddsFormat();
  const meQuery = useMeQuery(Boolean(session?.userId));
  const unreadQuery = useUnreadCountQuery();
  const discipline = useDisciplineMutation();
  const rest = useRestMutation();
  const me = meQuery.data;
  const unread = unreadQuery.data?.unread ?? 0;
  const loggedIn = isLoggedIn(session);
  const [refreshing, setRefreshing] = useState(false);
  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([meQuery.refetch(), unreadQuery.refetch()]);
    } finally {
      setRefreshing(false);
    }
  };
  const rested = Boolean(me?.streak.rested);

  const toggleDiscipline = async (next: boolean) => {
    try {
      await discipline.mutateAsync(next);
      toast.show(next ? "连败保护已开启" : "连败保护已关闭", "success");
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  const toggleRest = async (next: boolean) => {
    try {
      await rest.mutateAsync(next);
      toast.show(next ? "好，今晚先到这里" : "已恢复，今晚可以继续看", "success");
    } catch (e) {
      toast.show(errorText(e), "error");
    }
  };

  const confirmLogout = () => {
    Alert.alert("退出登录", "退出后会回到设备账户，手机号登录的数据不会丢失。", [
      { text: "取消", style: "cancel" },
      {
        text: "退出",
        style: "destructive",
        onPress: async () => {
          await logout();
          // 账号级偏好不能留给下一位使用同一设备的人。
          setPersona("zhuanjia");
          setOddsFormat("decimal");
          setAvatarUri(null);
          toast.show("已退出，回到设备账户", "info");
        },
      },
    ]);
  };

  return (
    <AppScreen bottom={false}>
      <AppHeader
        title="我的"
        subtitle="球多多 · AI 预测"
        showAssistant={false}
        right={
          <View>
            <IconButton name="mail-outline" onPress={() => router.push("/inbox")} accessibilityLabel="站内信" size={18} />
            {unread > 0 ? <View style={styles.unreadDot} /> : null}
          </View>
        }
      />
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.brand} />}
      >
        {meQuery.isError ? (
          <ErrorState compact message="账号状态暂时取不到，先显示本机偏好。" onRetry={() => meQuery.refetch()} />
        ) : null}
        <Card onPress={() => router.push("/settings/profile")} accessibilityLabel="编辑个人资料" style={styles.profile}>
          <Avatar source={avatarUri ? { uri: avatarUri } : meta.avatar} fallbackSource={meta.avatar} size={62} online />
          <View style={styles.profileText}>
            <Text variant="h2">{me?.displayName || session?.displayName || "球多多用户"}</Text>
            <Text variant="caption" color={colors.muted}>
              {loggedIn ? me?.phone ?? me?.email ?? "手机号已绑定" : "设备账户 · 绑定手机可跨设备"}
            </Text>
            <View style={styles.badges}>
              <Chip label={meta.name} tone="positive" />
              {me?.streak.active ? <Chip label={`连败 ${me.streak.streak}`} tone="negative" /> : null}
              {rested ? <Chip label="休息中" tone="amber" /> : null}
            </View>
          </View>
          <Icon name="chevron-forward" size={16} color={colors.subtle} />
        </Card>

        <View style={styles.quick}>
          <Quick label="收件箱" value={unread > 0 ? `${unread} 条未读` : "暂无未读"} icon="mail-outline" onPress={() => router.push("/inbox")} />
          <Quick label="关注" value="查看列表" icon="heart-outline" onPress={() => router.push("/watch")} />
          <Quick label="今日预测" value="查看今日" icon="analytics-outline" onPress={() => router.navigate("/(tabs)")} />
        </View>

        <SettingsGroup title="账户">
          <SettingsRow
            title="会员与权益"
            subtitle="Pro 竞彩 / Max 全市场 + AI 计划"
            icon="card-outline"
            onPress={() => router.push("/membership")}
          />
          <SettingsRow
            title="我的记录"
            subtitle="票单、周报、公开账本"
            icon="receipt-outline"
            onPress={() => router.push("/records")}
            last
          />
        </SettingsGroup>

        <SettingsGroup title="助理">
          <SettingsRow
            title="助理风格"
            subtitle="同一组数字，不同说话方式"
            value={meta.name}
            icon="sparkles-outline"
            onPress={() => router.push("/settings/persona")}
          />
          <SettingsRow
            title="它记得你什么"
            subtitle={`${me?.memories.length ?? 0} 条记忆，可见可删`}
            icon="bookmark-outline"
            onPress={() => router.push("/settings/memories")}
            last
          />
        </SettingsGroup>

        <SettingsGroup title="助理技能">
          <SettingsRow
            title="串关参谋"
            subtitle="2–6 场组合、相关性与四维体检"
            icon="git-merge-outline"
            onPress={() => router.push("/tools/parlay")}
          />
          <SettingsRow
            title="抽水计算"
            subtitle="三向赔率 → 真实抽水"
            icon="water-outline"
            onPress={() => router.push("/tools/rake")}
          />
          <SettingsRow
            title="赔率换算"
            subtitle="欧 / 港 / 印尼 / 美式"
            icon="swap-horizontal-outline"
            onPress={() => router.push("/tools/odds")}
          />
          <SettingsRow
            title="仓位计算"
            subtitle="凯利分数与单注上限"
            icon="stats-chart-outline"
            onPress={() => router.push("/tools/stake")}
          />
          <SettingsRow
            title="回本线"
            subtitle="这个赔率要赢多少才不亏"
            icon="analytics-outline"
            onPress={() => router.push("/tools/break-even")}
            last
          />
        </SettingsGroup>

        <SettingsGroup title="纪律">
          <SettingsRow
            title="连败保护"
            subtitle="连输 3 场后，加注前必须二次确认"
            right={
              <Toggle
                value={me?.disciplineOn ?? true}
                onChange={toggleDiscipline}
                label="连败保护"
                disabled={!session || discipline.isPending}
              />
            }
            icon="shield-checkmark-outline"
          />
          <SettingsRow
            title={rested ? "今天休息中" : "今天不看了"}
            subtitle={rested ? "明晚预测照常等你" : "随时可以停，反悔也能恢复"}
            right={
              <Toggle
                value={rested}
                onChange={toggleRest}
                label="休息模式"
                disabled={!session || rest.isPending}
              />
            }
            icon="moon-outline"
          />
          <SettingsRow
            title="合规中心"
            subtitle="自排除、自评、求助热线"
            icon="medkit-outline"
            onPress={() => router.push("/settings/compliance")}
            last
          />
        </SettingsGroup>

        <SettingsGroup title="偏好">
          <SettingsRow
            title="赔率格式"
            value={{ decimal: "欧洲盘", hk: "香港盘", indo: "印尼盘", american: "美式盘" }[oddsFormat]}
            icon="swap-horizontal-outline"
            onPress={() => router.push("/settings/preferences")}
          />
          <SettingsRow
            title="通知设置"
            subtitle="渠道、静默时段、每日上限"
            icon="notifications-outline"
            onPress={() => router.push("/settings/notifications")}
          />
          <SettingsRow
            title="隐私与数据"
            subtitle="导出、注销、数据说明"
            icon="lock-closed-outline"
            onPress={() => router.push("/settings/privacy")}
          />
          <SettingsRow
            title="关于球多多"
            subtitle="版本、法律文本、数据来源"
            icon="information-circle-outline"
            onPress={() => router.push("/settings/about")}
            last
          />
        </SettingsGroup>

        <View style={styles.accountActions}>
          {loggedIn ? (
            <Button label="退出登录" variant="secondary" onPress={confirmLogout} fullWidth />
          ) : (
            <Button label="手机号登录 / 注册" onPress={() => router.push("/auth/login")} fullWidth />
          )}
          <Text variant="caption" color={colors.subtle} center style={styles.footer}>{copy.footer}</Text>
        </View>
      </ScrollView>
    </AppScreen>
  );
}

function Quick({
  label,
  value,
  icon,
  onPress,
}: {
  label: string;
  value: string;
  icon: React.ComponentProps<typeof Icon>["name"];
  onPress: () => void;
}) {
  return (
    <Card onPress={onPress} accessibilityLabel={label} style={styles.quickCard}>
      <Icon name={icon} size={18} color={colors.muted} />
      <View style={styles.quickText}>
        <Text variant="smallStrong">{label}</Text>
        <Text variant="caption" color={colors.muted} numberOfLines={1}>{value}</Text>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: layout.pagePadding, paddingTop: spacing.sm, paddingBottom: spacing.x7, gap: spacing.xl },
  profile: { flexDirection: "row", alignItems: "center", gap: spacing.base, padding: spacing.x3 },
  profileText: { flex: 1, gap: 3 },
  badges: { flexDirection: "row", gap: spacing.xs, flexWrap: "wrap", marginTop: 2 },
  unreadDot: {
    position: "absolute",
    right: 7,
    top: 7,
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.danger,
    borderWidth: 1,
    borderColor: colors.bg,
  },
  quick: { flexDirection: "row", gap: spacing.sm },
  quickCard: {
    flex: 1,
    padding: spacing.lg,
    minHeight: 88,
    gap: spacing.sm,
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  quickText: { gap: 2 },
  accountActions: { marginTop: spacing.sm, gap: spacing.base },
  footer: { lineHeight: 18, paddingHorizontal: spacing.base },
});
