import { StyleSheet, Text, View } from "react-native";

export default function RecordsScreen() {
  return (
    <View style={styles.screen}>
      <Text style={styles.title}>记录</Text>
      <Text style={styles.body}>
        票单、周报、归因与公开账本将在移动端逐项迁移。
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F5F4EF",
    paddingHorizontal: 18,
    paddingTop: 18,
  },
  title: {
    fontSize: 22,
    fontWeight: "600",
    color: "#15211B",
  },
  body: {
    marginTop: 10,
    fontSize: 13,
    lineHeight: 20,
    color: "#6B756F",
  },
});
