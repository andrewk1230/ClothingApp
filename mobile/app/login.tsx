import { useRouter } from "expo-router";
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
} from "react-native";

import { getColors } from "../lib/theme";

export default function LoginScreen() {
  const router = useRouter();
  const scheme = useColorScheme();
  const colors = getColors(scheme);

  const handleGoogleSignIn = async () => {
    // TODO: Phase 5 — Supabase OAuth with Google
  };

  const handleAppleSignIn = async () => {
    // TODO: Phase 5 — Supabase OAuth with Apple
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Text style={[styles.title, { color: colors.text }]}>Sign In</Text>
      <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
        Unlock filters, saved items, and search history
      </Text>

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.border }]}
          onPress={handleGoogleSignIn}
        >
          <Text style={[styles.buttonText, { color: colors.text }]}>
            Continue with Google
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.accent }]}
          onPress={handleAppleSignIn}
        >
          <Text style={[styles.buttonText, { color: colors.accentText }]}>
            Continue with Apple
          </Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity onPress={() => router.back()}>
        <Text style={[styles.skipText, { color: colors.textSecondary }]}>
          Continue as Guest
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    textAlign: "center",
    marginBottom: 48,
  },
  buttonGroup: {
    width: "100%",
    gap: 12,
    marginBottom: 24,
  },
  button: {
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "transparent",
  },
  buttonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  skipText: {
    fontSize: 16,
  },
});
