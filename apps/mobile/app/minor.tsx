import { Image, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Card, Icon, Text } from "@/components/ui";
import { useLegalQuery } from "@/features/account/queries";
import { colors, layout, spacing } from "@/theme/tokens";

export default function MinorScreen() {
  const router = useRouter();
  const legal = useLegalQuery();

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.hero}>
        <Image
          source={require("../assets/mascot/zhuanjia.png")}
          style={styles.avatar}
          resizeMode="cover"
        />
        <Text variant="overline" color={colors.brand}>未成年模式</Text>
        <Text variant="display" center style={styles.title}>只看，不参与</Text>
        <Text variant="body" color={colors.muted} center style={styles.lead}>
          未满 18 周岁不能购买彩票。球多多只开放公开账本给你了解分析怎么做，不展示记注和个性化预测。
        </Text>
      </View>

      <Card style={styles.card}>
        <View style={styles.row}>
          <Icon name="book-outline" size={18} color={colors.brand} />
          <Text variant="bodyStrong" style={styles.flex}>公开账本</Text>
          <Text variant="caption" color={colors.brand}>可查看</Text>
        </View>
        <View style={styles.row}>
          <Icon name="close-circle-outline" size={18} color={colors.danger} />
          <Text variant="bodyStrong" style={styles.flex}>预测流 / 记注 / 记录</Text>
          <Text variant="caption" color={colors.danger}>不开放</Text>
        </View>
      </Card>

      <View style={styles.actions}>
        <Button label="打开公开账本" onPress={() => router.push("/records/ledger")} fullWidth />
        <Button
          label="服务说明与隐私"
          variant="secondary"
          onPress={() => router.push({ pathname: "/legal", params: { doc: "terms" } })}
          fullWidth
        />
      </View>

      <Card tone="amber" style={styles.help}>
        <Text variant="smallStrong">如果你在为难</Text>
        <Text variant="small" color={colors.muted} style={styles.helpText}>
          可以联系信任的成年人，或拨打当地心理援助热线。
          {legal.data?.helpline ? ` 球多多记录的求助热线：${legal.data.helpline}。` : ""}
        </Text>
      </Card>
      <Text variant="caption" color={colors.subtle} center style={styles.footer}>
        年龄状态只在本机记录，不收集出生日期。更换设备后需要重新确认。
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, width: "100%", maxWidth: layout.maxWidth, alignSelf: "center", backgroundColor: colors.bg, paddingHorizontal: layout.pagePadding },
  hero: { alignItems: "center", marginTop: spacing.x4, gap: spacing.xs },
  avatar: { width: 92, height: 92, borderRadius: 46, marginBottom: spacing.base },
  title: { marginTop: spacing.xs },
  lead: { maxWidth: 320, lineHeight: 22, marginTop: spacing.xs },
  card: { marginTop: spacing.x4, gap: spacing.base },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  flex: { flex: 1 },
  actions: { marginTop: spacing.x4, gap: spacing.sm },
  help: { marginTop: spacing.x4, gap: spacing.xs },
  helpText: { lineHeight: 19 },
  footer: { marginTop: spacing.base, lineHeight: 17 },
});
