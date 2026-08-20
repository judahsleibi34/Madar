import { useEffect, useRef } from "react";
import {
  Animated,
  Easing,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { router } from "expo-router";

const COLORS = {
  cream: "#F3EEE4",
  creamDark: "#E9DFD0",
  navy: "#10172F",
  red: "#852C21",
};

export default function SplashScreen() {
  const { width, height } = useWindowDimensions();

  const logoOpacity = useRef(new Animated.Value(0)).current;
  const logoScale = useRef(new Animated.Value(0.88)).current;

  const textOpacity = useRef(new Animated.Value(0)).current;
  const textY = useRef(new Animated.Value(18)).current;

  const screenOpacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.parallel([
        Animated.timing(logoOpacity, {
          toValue: 1,
          duration: 800,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),

        Animated.spring(logoScale, {
          toValue: 1,
          friction: 7,
          tension: 35,
          useNativeDriver: true,
        }),
      ]),

      Animated.parallel([
        Animated.timing(textOpacity, {
          toValue: 1,
          duration: 550,
          useNativeDriver: true,
        }),

        Animated.timing(textY, {
          toValue: 0,
          duration: 550,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),

      Animated.delay(1600),

      Animated.timing(screenOpacity, {
        toValue: 0,
        duration: 600,
        useNativeDriver: true,
      }),
    ]).start(({ finished }) => {
      if (finished) {
        router.replace("/landing");
      }
    });
  }, []);

  return (
    <View
      style={[
        styles.screen,
        {
          width,
          height,
        },
      ]}
    >
      {/* Decorative Madar background */}
      <View style={styles.redGlow} />
      <View style={styles.navyGlow} />

      <Animated.View
        style={[
          styles.content,
          {
            opacity: screenOpacity,
          },
        ]}
      >
        <Animated.Image
          source={require("../../assets/branding/madar-header.png")}
          resizeMode="contain"
          style={[
            styles.logo,
            {
              width: Math.min(width * 0.82, 360),
              opacity: logoOpacity,
              transform: [{ scale: logoScale }],
            },
          ]}
        />

        <Animated.View
          style={{
            opacity: textOpacity,
            transform: [{ translateY: textY }],
          }}
        >
          <Text style={styles.welcome}>
            Welcome to
          </Text>

          <Text style={styles.brand}>
            Madar Portal
          </Text>

          <View style={styles.line} />
        </Animated.View>
      </Animated.View>

      <View style={styles.bottom}>
        <Text style={styles.bottomText}>
          مدار
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: COLORS.cream,
    overflow: "hidden",
  },

  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 28,
    zIndex: 2,
  },

  logo: {
    height: 230,
    marginBottom: 34,
  },

  welcome: {
    fontSize: 23,
    fontWeight: "500",
    color: COLORS.navy,
    textAlign: "center",
    letterSpacing: 0.2,
  },

  brand: {
    marginTop: 5,
    fontSize: 39,
    lineHeight: 46,
    fontWeight: "800",
    color: COLORS.red,
    textAlign: "center",
    letterSpacing: -1,
  },

  line: {
    alignSelf: "center",
    width: 58,
    height: 4,
    borderRadius: 20,
    backgroundColor: COLORS.navy,
    marginTop: 20,
  },

  redGlow: {
    position: "absolute",
    width: 330,
    height: 330,
    borderRadius: 999,
    backgroundColor: "rgba(155, 24, 43, 0.07)",
    top: -150,
    right: -140,
  },

  navyGlow: {
    position: "absolute",
    width: 400,
    height: 400,
    borderRadius: 999,
    backgroundColor: "rgba(16, 23, 47, 0.045)",
    bottom: -240,
    left: -170,
  },

  bottom: {
    position: "absolute",
    bottom: 32,
    left: 0,
    right: 0,
    alignItems: "center",
  },

  bottomText: {
    color: COLORS.red,
    fontSize: 17,
    fontWeight: "600",
    opacity: 0.65,
  },
});
