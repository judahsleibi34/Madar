import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";

import MadarLogo from "../components/branding/MadarLogo";
import { colors, radius, spacing } from "../constants/theme";

export default function LandingScreen() {
  return (
    <SafeAreaView style={styles.screen} edges={["top", "bottom"]}>
      <View pointerEvents="none" style={styles.backgroundLogo}>
        <MadarLogo width={520} />
      </View>

      <View style={styles.container}>
        <View>
          <View style={styles.header}>
            <Text style={styles.headerTitle}>MADAR PORTAL</Text>
          </View>

          <View style={styles.hero}>
            <Text style={styles.h2}>
              Your work,{"\n"}
              wherever you are.
            </Text>

            <Text style={styles.h3}>
              Access your Madar workspace, services and daily work from one place.
            </Text>
          </View>
        </View>

        <View style={styles.authCard}>
          <Text style={styles.authTitle}>Continue to Madar</Text>
          <Text style={styles.authSubtitle}>
            Choose how you want to continue.
          </Text>

          <Pressable
            style={({ pressed }) => [
              styles.primaryButton,
              pressed && styles.pressed,
            ]}
            onPress={() => {}}
          >
            <Text style={styles.primaryButtonText}>Sign in to Madar</Text>
          </Pressable>

          <Pressable
            style={({ pressed }) => [
              styles.googleButton,
              pressed && styles.pressed,
            ]}
            onPress={() => {}}
          >
            <View style={styles.googleIconWrap}>
              <Svg width={19} height={19} viewBox="0 0 18 18">
                <Path
                  fill="#4285F4"
                  d="M17.64 9.205c0-.638-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.797 2.716v2.258h2.909c1.702-1.567 2.684-3.874 2.684-6.614z"
                />
                <Path
                  fill="#34A853"
                  d="M9 18c2.43 0 4.468-.806 5.956-2.181l-2.909-2.258c-.806.54-1.835.859-3.047.859-2.344 0-4.328-1.585-5.037-3.714H.956v2.332A9 9 0 0 0 9 18z"
                />
                <Path
                  fill="#FBBC05"
                  d="M3.963 10.706A5.41 5.41 0 0 1 3.682 9c0-.592.102-1.167.281-1.706V4.962H.956A9 9 0 0 0 0 9c0 1.45.347 2.822.956 4.038l3.007-2.332z"
                />
                <Path
                  fill="#EA4335"
                  d="M9 3.58c1.321 0 2.507.454 3.441 1.346l2.581-2.581C13.464.892 11.426 0 9 0A9 9 0 0 0 .956 4.962l3.007 2.332C4.672 5.165 6.656 3.58 9 3.58z"
                />
              </Svg>
            </View>

            <Text style={styles.googleButtonText}>
              Continue with Google
            </Text>
          </Pressable>

          <Pressable
            style={({ pressed }) => [
              styles.guestButton,
              pressed && styles.pressed,
            ]}
            onPress={() => {}}
          >
            <Ionicons
              name="person-outline"
              size={17}
              color={colors.secondaryText}
            />

            <Text style={styles.guestButtonText}>
              Continue as Guest
            </Text>
          </Pressable>

          <View style={styles.registerRow}>
            <Text style={styles.registerText}>New to Madar?</Text>

            <Pressable onPress={() => {}}>
              <Text style={styles.registerLink}>
                Create account
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },

  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 26,
    justifyContent: "space-between",
  },

  backgroundLogo: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: "center",
    justifyContent: "center",
    opacity: 0.75,
  },

  header: {
    alignItems: "flex-start",
    paddingTop: 8,
  },

  headerTitle: {
    fontSize: 36,
    lineHeight: 42,
    fontWeight: "700",
    letterSpacing: -0.4,
    color: colors.red,
  },

  hero: {
    marginTop: 42,
  },

  h2: {
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "700",
    letterSpacing: -0.5,
    color: colors.navy,
  },

  h3: {
    marginTop: 14,
    maxWidth: 320,
    fontSize: 17,
    lineHeight: 25,
    fontWeight: "500",
    color: colors.secondaryText,
  },

  authCard: {
    paddingHorizontal: 18,
    paddingVertical: 18,
    width: "100%",
    alignSelf: "center",
  },

  authTitle: {
    fontSize: 18,
    lineHeight: 24,
    fontWeight: "700",
    color: colors.navy,
    textAlign: "center",
  },

  authSubtitle: {
    marginTop: 3,
    marginBottom: 16,
    fontSize: 14,
    lineHeight: 20,
    color: colors.secondaryText,
    textAlign: "center",
  },

  primaryButton: {
    height: 50,
    borderRadius: radius.default,
    backgroundColor: colors.red,
    alignItems: "center",
    justifyContent: "center",
  },

  primaryButtonText: {
    fontSize: 15,
    lineHeight: 20,
    fontWeight: "600",
    color: colors.white,
  },

  googleButton: {
    height: 50,
    marginTop: 10,
    borderRadius: radius.default,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.white,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },

  googleIconWrap: {
    position: "absolute",
    left: 16,
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },

  googleButtonText: {
    fontSize: 15,
    lineHeight: 20,
    fontWeight: "600",
    color: colors.navy,
  },




  guestButton: {
    height: 42,
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
  },

  guestButtonText: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "600",
    color: colors.secondaryText,
  },

  registerRow: {
    marginTop: 12,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 6,
  },

  registerText: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.secondaryText,
  },

  registerLink: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "700",
    color: colors.red,
  },

  pressed: {
    opacity: 0.76,
  },
});












