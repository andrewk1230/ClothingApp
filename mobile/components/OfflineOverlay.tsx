import NetInfo from "@react-native-community/netinfo";
import { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { useTheme } from "../hooks/useTheme";

const OFFLINE_DEBOUNCE_MS = 1000;

/**
 * Full-screen "No connection" overlay (PRD section 11). Rendered above the
 * navigator; shows after connectivity has been down for ~1s (debounced to
 * avoid flicker while NetInfo settles on app start) and auto-dismisses the
 * moment the device is back online.
 */
export default function OfflineOverlay() {
  const { colors } = useTheme();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;

    const unsubscribe = NetInfo.addEventListener((state) => {
      const isOffline =
        state.isConnected === false && state.isInternetReachable !== true;
      if (isOffline) {
        if (!timer) {
          timer = setTimeout(() => {
            setOffline(true);
            timer = null;
          }, OFFLINE_DEBOUNCE_MS);
        }
      } else {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        setOffline(false);
      }
    });

    return () => {
      unsubscribe();
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, []);

  if (!offline) {
    return null;
  }

  // Rendered inside an RN <Modal> so it also covers screens presented as
  // native modals (segmentation, login, onboarding), which sit above any
  // absolutely-positioned sibling view.
  return (
    <Modal
      visible
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={() => {
        // The overlay dismisses itself when connectivity returns.
      }}
    >
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <Text style={styles.icon}>📡</Text>
        <Text style={[styles.title, { color: colors.text }]}>No connection</Text>
        <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
          GrailSeeker needs an internet connection. We&apos;ll reconnect
          automatically.
        </Text>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 32,
  },
  icon: {
    fontSize: 56,
    marginBottom: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    textAlign: "center",
    lineHeight: 24,
  },
});
