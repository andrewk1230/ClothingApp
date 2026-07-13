import { makeRedirectUri } from "expo-auth-session";
import { getQueryParams } from "expo-auth-session/build/QueryParams";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { useTheme } from "../hooks/useTheme";
import { isSupabaseConfigured, supabase } from "../lib/supabase";

WebBrowser.maybeCompleteAuthSession();

type Provider = "google" | "apple";

const redirectTo = makeRedirectUri();

async function createSessionFromUrl(url: string): Promise<void> {
  const { params, errorCode } = getQueryParams(url);
  if (errorCode) {
    throw new Error(errorCode);
  }

  const { access_token, refresh_token } = params;
  if (!access_token || !refresh_token) {
    throw new Error("Sign-in did not return a session. Please try again.");
  }

  const { error } = await supabase.auth.setSession({
    access_token,
    refresh_token,
  });
  if (error) {
    throw error;
  }
}

export default function LoginScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const [pendingProvider, setPendingProvider] = useState<Provider | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const signInWith = async (provider: Provider) => {
    if (pendingProvider) return;

    if (!isSupabaseConfigured) {
      setErrorMessage("Sign-in is not configured yet");
      return;
    }

    setPendingProvider(provider);
    setErrorMessage(null);
    try {
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo,
          skipBrowserRedirect: true,
        },
      });
      if (error) throw error;
      if (!data?.url) {
        throw new Error("Couldn't start sign-in. Please try again.");
      }

      const result = await WebBrowser.openAuthSessionAsync(data.url, redirectTo);
      if (result.type !== "success") {
        // User cancelled or dismissed the browser — stay silent.
        return;
      }

      await createSessionFromUrl(result.url);
      router.back();
    } catch (e) {
      setErrorMessage(
        e instanceof Error && e.message
          ? e.message
          : "Sign-in failed. Please try again."
      );
    } finally {
      setPendingProvider(null);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Text style={[styles.title, { color: colors.text }]}>Sign In</Text>
      <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
        Unlock filters, saved items, and search history
      </Text>

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[
            styles.button,
            { backgroundColor: colors.surface, borderColor: colors.border },
          ]}
          onPress={() => signInWith("google")}
          disabled={pendingProvider !== null}
        >
          {pendingProvider === "google" ? (
            <ActivityIndicator color={colors.text} />
          ) : (
            <Text style={[styles.buttonText, { color: colors.text }]}>
              Continue with Google
            </Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.accent }]}
          onPress={() => signInWith("apple")}
          disabled={pendingProvider !== null}
        >
          {pendingProvider === "apple" ? (
            <ActivityIndicator color={colors.accentText} />
          ) : (
            <Text style={[styles.buttonText, { color: colors.accentText }]}>
              Continue with Apple
            </Text>
          )}
        </TouchableOpacity>
      </View>

      {errorMessage && (
        <Text style={[styles.errorText, { color: colors.error }]}>
          {errorMessage}
        </Text>
      )}

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
    justifyContent: "center",
    minHeight: 54,
    borderWidth: 1,
    borderColor: "transparent",
  },
  buttonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  errorText: {
    fontSize: 14,
    textAlign: "center",
    marginBottom: 24,
  },
  skipText: {
    fontSize: 16,
  },
});
