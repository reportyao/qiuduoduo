import { Tabs } from "expo-router";
import { View } from "react-native";
import { useUnreadCountQuery } from "@/features/inbox/queries";
import { BottomTabBar } from "@/components/BottomTabBar";
import { FloatingAssistant } from "@/components/FloatingAssistant";

export default function TabsLayout() {
  const { data } = useUnreadCountQuery();
  const unread = data?.unread ?? 0;

  return (
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={{ headerShown: false }}
        tabBar={(props) => <BottomTabBar {...props} unread={unread} />}
      >
        <Tabs.Screen name="index" options={{ title: "首页" }} />
        <Tabs.Screen name="tools" options={{ title: "工具" }} />
        <Tabs.Screen name="records" options={{ title: "记录" }} />
        <Tabs.Screen name="me" options={{ title: "我的" }} />
      </Tabs>
      {/* 常驻在 4 个 Tab 之上，不随页面滚动 */}
      <FloatingAssistant />
    </View>
  );
}
