import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#0E6B4F",
        tabBarInactiveTintColor: "#6B756F",
        tabBarLabelStyle: {
          fontSize: 11,
        },
        tabBarStyle: {
          backgroundColor: "#FFFFFF",
          borderTopColor: "#E9E7E0",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "首页",
        }}
      />
      <Tabs.Screen
        name="tools"
        options={{
          title: "工具",
        }}
      />
      <Tabs.Screen
        name="records"
        options={{
          title: "记录",
        }}
      />
      <Tabs.Screen
        name="me"
        options={{
          title: "我的",
        }}
      />
    </Tabs>
  );
}
