import {
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";

export default function LoginScreen() {
  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.container}>
        <Text style={styles.title}>
          Sign in
        </Text>

        <Text style={styles.subtitle}>
          Login screen comes next.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },

  container: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 26,
  },

  title: {
    fontSize: 38,
    fontWeight: "700",
    color: "#17191C",
  },

  subtitle: {
    marginTop: 10,
    fontSize: 17,
    color: "#71767C",
  },
});
