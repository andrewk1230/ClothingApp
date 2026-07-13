import AsyncStorage from "@react-native-async-storage/async-storage";
import { Stack, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";

import OfflineOverlay from "../components/OfflineOverlay";
import { ONBOARDING_COMPLETE_KEY } from "../constants/config";
import { ThemeProvider, useTheme } from "../hooks/useTheme";

function RootNavigator() {
  const { colors, scheme } = useTheme();
  const router = useRouter();
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(ONBOARDING_COMPLETE_KEY)
      .then((value) => setNeedsOnboarding(value !== "true"))
      .catch(() => setNeedsOnboarding(false));
  }, []);

  useEffect(() => {
    // Redirect after the navigator has mounted (needsOnboarding only becomes
    // true after the flag is read, and the <Stack> renders on that pass).
    if (needsOnboarding) {
      router.replace("/onboarding");
    }
  }, [needsOnboarding, router]);

  // Hold the splash frame until the onboarding flag has been read so the
  // home screen never flashes before the redirect.
  if (needsOnboarding === null) {
    return null;
  }

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
          options={{
            headerShown: false,
            presentation: "fullScreenModal",
            gestureEnabled: false,
          }}
        />
        <Stack.Screen
          name="login"
          options={{ title: "Sign In", presentation: "modal" }}
        />
      </Stack>
      <OfflineOverlay />
    </>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <RootNavigator />
    </ThemeProvider>
  );
}
