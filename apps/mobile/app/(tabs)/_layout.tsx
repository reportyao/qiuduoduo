import { Tabs } from "expo-router";
import { View } from "react-native";
import { useUnreadCountQuery } from "@/features/inbox/queries";
import { BottomTabBar } from "@/components/BottomTabBar";
import { FloatingAssistant } from "@/components/FloatingAssistant";
import { GlobalMatchPicker } from "@/features/home/components/GlobalMatchPicker";

export default function TabsLayout() {
  const { data } = useUnreadCountQuery();
  const unread = data?.unread ?? 0;

  return (
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={{ headerShown: false }}
        tabBar={(props) => <BottomTabBar {...props} unread={unread} />}
      >
        <Tabs.Screen name="index" options={{ title: "助理" }} />
        <Tabs.Screen name="matches" options={{ title: "比赛" }} />
        <Tabs.Screen name="records" options={{ title: "记录" }} />
        <Tabs.Screen name="me" options={{ title: "我的" }} />
      </Tabs>
      {/* 常驻在 4 个 Tab 之上，不随页面滚动；点击弹出今日比赛 */}
      <FloatingAssistant />
      <GlobalMatchPicker />
    </View>
  );
}
