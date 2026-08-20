import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";

import MadarLogo from "../components/branding/MadarLogo";

export default function LandingScreen() {
  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.container}>

        <View style={styles.header}>
          <MadarLogo width={145} />
        </View>

        <View style={styles.hero}>
          <Text style={styles.smallTitle}>
            MADAR PORTAL
          </Text>

          <Text style={styles.title}>
            Your work,
            {"\n"}
            wherever you are.
          </Text>

          <Text style={styles.description}>
            Access Madar from your phone and stay connected
            to your work, requests and daily activities.
          </Text>

          <View style={styles.tags}>
            <View style={styles.tag}>
              <Text style={styles.tagText}>
                Requests
              </Text>
            </View>

            <View style={styles.tag}>
              <Text style={styles.tagText}>
                Tasks
              </Text>
            </View>

            <View style={styles.tag}>
              <Text style={styles.tagText}>
                Services
              </Text>
            </View>
          </View>
        </View>

        <View style={styles.actions}>
          <Pressable
            style={({ pressed }) => [
              styles.button,
              pressed && styles.buttonPressed,
            ]}
            onPress={() => router.push("/login")}
          >
            <Text style={styles.buttonText}>
              Continue
            </Text>
          </Pressable>

          <Text style={styles.footer}>
            Madar Portal
          </Text>
        </View>

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
    paddingHorizontal: 26,
    paddingTop: 15,
    paddingBottom: 18,
  },

  header: {
    alignItems: "flex-start",
  },

  hero: {
    flex: 1,
    justifyContent: "center",
  },

  smallTitle: {
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 2,
    color: "#777C82",
    marginBottom: 18,
  },

  title: {
    fontSize: 43,
    lineHeight: 49,
    letterSpacing: -1.5,
    fontWeight: "700",
    color: "#17191C",
  },

  description: {
    marginTop: 24,
    fontSize: 17,
    lineHeight: 27,
    color: "#696E74",
    maxWidth: 350,
  },

  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 9,
    marginTop: 30,
  },

  tag: {
    paddingHorizontal: 15,
    paddingVertical: 9,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#E3E5E8",
    backgroundColor: "#F8F9FA",
  },

  tagText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#51555A",
  },

  actions: {
    width: "100%",
  },

  button: {
    height: 58,
    backgroundColor: "#17191C",
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center",
  },

  buttonPressed: {
    opacity: 0.82,
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
  },

  footer: {
    textAlign: "center",
    marginTop: 16,
    color: "#A0A4A8",
    fontSize: 12,
  },
});
