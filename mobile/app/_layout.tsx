import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useColorScheme } from "react-native";

import { getColors } from "../lib/theme";

export default function RootLayout() {
  const scheme = useColorScheme();
  const colors = getColors(scheme);

  return (
    <>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="segmentation"
          options={{ title: "Select Item", presentation: "modal" }}
        />
        <Stack.Screen name="results" options={{ title: "Results" }} />
        <Stack.Screen name="listing/[id]" options={{ title: "Listing" }} />
        <Stack.Screen
          name="onboarding"
          options={{ headerShown: false, presentation: "modal" }}
        />
        <Stack.Screen
          name="login"
          options={{ title: "Sign In", presentation: "modal" }}
        />
      </Stack>
    </>
  );
}
