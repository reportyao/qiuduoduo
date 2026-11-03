import { useEffect, useRef, useState } from "react";
import { Alert, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import * as Clipboard from "expo-clipboard";
import { SettingsPage } from "@/components/SettingsPage";
import {
  Button,
  Card,
  SettingsGroup,
  SettingsRow,
  Text,
  useToast,
} from "@/components/ui";
import {
  useDeleteAccountMutation,
  useExportQuery,
} from "@/features/account/queries";
import { errorText } from "@/lib/errors";
import { colors } from "@/theme/tokens";

export default function PrivacyScreen() {
  const router = useRouter();
  const toast = useToast();
  const [exportRequested, setExportRequested] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const exportQuery = useExportQuery(exportRequested);
  const deleteAccount = useDeleteAccountMutation();
  const copiedRef = useRef(false);

  useEffect(() => {
    if (!exportQuery.data || copiedRef.current) return;
    copiedRef.current = true;
    void Clipboard.setStringAsync(JSON.stringify(exportQuery.data, null, 2))
      .then(() => toast.show("JSON 已复制到剪贴板", "success"))
      .catch(() => toast.show("复制失败，请重试", "error"));
  }, [exportQuery.data, toast]);

  const confirmDelete = () => {
    Alert.alert(
      "注销账号",
      "进入 7 天冷静期。期间用同一设备令牌登录即自动撤回注销；期满后数据会被清除。",
      [
        { text: "取消", style: "cancel" },
        {
          text: "确认注销",
          style: "destructive",
          onPress: async () => {
            try {
              const out = await deleteAccount.mutateAsync();
              setDeleted(true);
              toast.show(out.message, "warning");
            } catch (e) {
              toast.show(errorText(e), "error");
            }
          },
        },
      ],
    );
  };

  return (
    <SettingsPage title="隐私与数据" subtitle="你能拿走，也能删掉" onBack={() => router.back()}>
      <Card tone="green">
        <Text variant="small" color={colors.muted} style={styles.note}>
          解球不卖用户数据、不上传通讯录、不收集出生日期。下注金额只有你自己看得到，公开账本只展示判断本身。
        </Text>
      </Card>

      <SettingsGroup title="数据">
        <SettingsRow
          title="记忆"
          subtitle="查看或删除助理记住的偏好"
          icon="bookmark-outline"
          onPress={() => router.push("/settings/memories")}
        />
        <SettingsRow
          title="导出数据"
          subtitle="JSON 复制到剪贴板，包含账号、注单与记忆"
          icon="download-outline"
          onPress={() => {
            copiedRef.current = false;
            setExportRequested(true);
          }}
          right={
            exportQuery.isFetching ? (
              <Text variant="caption" color={colors.muted}>导出中…</Text>
            ) : undefined
          }
        />
        <SettingsRow
          title="数据来源"
          subtitle="竞彩官方 SP / 国际盘 / xG / 赛程"
          icon="server-outline"
          onPress={() => router.push("/settings/about")}
          last
        />
      </SettingsGroup>

      {exportQuery.isError ? (
        <Text variant="caption" color={colors.danger}>{errorText(exportQuery.error)}</Text>
      ) : null}

      <SettingsGroup title="账号">
        <SettingsRow
          title={deleted ? "已进入 7 天冷静期" : "注销账号"}
          subtitle={deleted ? "同一设备登录即撤回注销；期满清除数据" : "7 天冷静期内可撤回"}
          icon="trash-outline"
          danger
          onPress={deleted ? undefined : confirmDelete}
          last
        />
      </SettingsGroup>

      <Button label="返回" variant="secondary" onPress={() => router.back()} fullWidth />
      <Text variant="caption" color={colors.subtle} center style={styles.note}>
        注销不会删除你已经生成的公开判断；公开账本中的判断不含个人金额。
      </Text>
    </SettingsPage>
  );
}

const styles = StyleSheet.create({
  note: { lineHeight: 19 },
});
