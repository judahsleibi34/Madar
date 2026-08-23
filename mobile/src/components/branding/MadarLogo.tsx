import { Image, StyleSheet, View } from "react-native";

type MadarLogoProps = {
  width?: number;
};

export default function MadarLogo({
  width = 220,
}: MadarLogoProps) {
  return (
    <View style={styles.container}>
      <Image
        source={require("../../../assets/branding/madar-header.png")}
        style={{
          width,
          height: width * 0.35,
        }}
        resizeMode="contain"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
  },
});
