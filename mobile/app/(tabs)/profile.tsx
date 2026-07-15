import Constants from "expo-constants";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import HistoryRow, { HistoryEntry } from "../../components/HistoryRow";
import { useAuth } from "../../hooks/useAuth";
import { ThemePreference, useTheme } from "../../hooks/useTheme";
import api from "../../lib/api";

interface RateLimitInfo {
  limit: number;
  used: number;
  remaining: number;
}

const APPEARANCE_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export default function ProfileScreen() {
  const { colors, preference, setPreference } = useTheme();
  const router = useRouter();
  const { isLoggedIn, email, loading: authLoading, signOut } = useAuth();

  const [history, setHistory] = useState<HistoryEntry[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [rateLimit, setRateLimit] = useState<RateLimitInfo | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const response = await api.get("/api/v1/history");
      setHistory(response.data ?? []);
    } catch {
      setHistoryError("Couldn't load your search history.");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const fetchRateLimit = useCallback(async () => {
    try {
      const response = await api.get("/api/v1/rate-limit");
      setRateLimit(response.data ?? null);
    } catch {
      // Rate limit display is best-effort; keep the last known value.
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (isLoggedIn) {
        fetchHistory();
        fetchRateLimit();
      }
    }, [isLoggedIn, fetchHistory, fetchRateLimit])
  );

  const handleDeleteEntry = useCallback((entryId: string) => {
    let previous: HistoryEntry[] | null = null;
    setHistory((current) => {
      previous = current;
      return current ? current.filter((entry) => entry.id !== entryId) : current;
    });
    api.delete(`/api/v1/history/${entryId}`).catch(() => {
      // Roll back the optimistic removal.
      setHistory(previous);
      Alert.alert(
        "Couldn't delete",
        "That search couldn't be removed. Please try again."
      );
    });
  }, []);

  const handleSignOut = useCallback(() => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign Out",
        style: "destructive",
        onPress: async () => {
          setSigningOut(true);
          const { error } = await signOut();
          setSigningOut(false);
          if (error) {
            Alert.alert("Sign out failed", error);
          }
        },
      },
    ]);
  }, [signOut]);

  if (authLoading) {
    return (
      <View style={[styles.centered, { backgroundColor: colors.background }]} />
    );
  }

  if (!isLoggedIn) {
    return (
      <View style={[styles.centered, { backgroundColor: colors.background }]}>
        <Text style={[styles.gateTitle, { color: colors.text }]}>Profile</Text>
        <Text style={[styles.gateSubtitle, { color: colors.textSecondary }]}>
          Sign in to view your search history and settings
        </Text>
        <TouchableOpacity
          style={[styles.gateButton, { backgroundColor: colors.accent }]}
          onPress={() => router.push("/login")}
        >
          <Text style={[styles.gateButtonText, { color: colors.accentText }]}>
            Sign In
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  const version = Constants.expoConfig?.version ?? "unknown";

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <Text style={[styles.email, { color: colors.text }]} numberOfLines={1}>
          {email ?? "Signed in"}
        </Text>
      </View>

      <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
        SEARCH HISTORY
      </Text>
      <View style={[styles.section, { backgroundColor: colors.surface }]}>
        {historyLoading && history === null ? (
          <View style={styles.sectionPlaceholder}>
            <ActivityIndicator color={colors.textSecondary} />
          </View>
        ) : historyError && (history === null || history.length === 0) ? (
          <View style={styles.sectionPlaceholder}>
            <Text
              style={[styles.placeholderText, { color: colors.textSecondary }]}
            >
              {historyError}
            </Text>
            <TouchableOpacity onPress={fetchHistory}>
              <Text style={[styles.retryText, { color: colors.text }]}>
                Retry
              </Text>
            </TouchableOpacity>
          </View>
        ) : history !== null && history.length === 0 ? (
          <View style={styles.sectionPlaceholder}>
            <Text
              style={[styles.placeholderText, { color: colors.textSecondary }]}
            >
              No searches yet — your history will appear here
            </Text>
          </View>
        ) : (
          (history ?? []).map((entry) => (
            <HistoryRow
              key={entry.id}
              entry={entry}
              onPress={() =>
                router.push({
                  pathname: "/results",
                  params: { historyId: entry.id },
                })
              }
              onDelete={() => handleDeleteEntry(entry.id)}
            />
          ))
        )}
      </View>

      <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
        SETTINGS
      </Text>
      <View style={[styles.section, { backgroundColor: colors.surface }]}>
        <View style={styles.settingRow}>
          <Text style={[styles.settingLabel, { color: colors.text }]}>
            Appearance
          </Text>
          <View
            style={[styles.segmented, { backgroundColor: colors.background }]}
          >
            {APPEARANCE_OPTIONS.map((option) => {
              const selected = preference === option.value;
              return (
                <TouchableOpacity
                  key={option.value}
                  style={[
                    styles.segment,
                    selected && { backgroundColor: colors.accent },
                  ]}
                  onPress={() => setPreference(option.value)}
                >
                  <Text
                    style={[
                      styles.segmentText,
                      {
                        color: selected
                          ? colors.accentText
                          : colors.textSecondary,
                      },
                    ]}
                  >
                    {option.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <Text style={[styles.settingLabel, { color: colors.text }]}>
            Searches today
          </Text>
          <Text style={[styles.settingValue, { color: colors.textSecondary }]}>
            {rateLimit ? `${rateLimit.used} of ${rateLimit.limit}` : "—"}
          </Text>
        </View>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <TouchableOpacity
          style={styles.settingRow}
          onPress={handleSignOut}
          disabled={signingOut}
        >
          <Text style={[styles.settingLabel, { color: colors.error }]}>
            {signingOut ? "Signing out…" : "Sign Out"}
          </Text>
        </TouchableOpacity>

        <View style={[styles.divider, { backgroundColor: colors.border }]} />

        <View style={styles.settingRow}>
          <Text style={[styles.settingLabel, { color: colors.text }]}>
            About
          </Text>
          <Text style={[styles.settingValue, { color: colors.textSecondary }]}>
            GrailSeeker v{version}
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingBottom: 48,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  gateTitle: {
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 8,
  },
  gateSubtitle: {
    fontSize: 16,
    marginBottom: 24,
    textAlign: "center",
  },
  gateButton: {
    padding: 16,
    borderRadius: 12,
    paddingHorizontal: 32,
  },
  gateButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  header: {
    marginBottom: 24,
  },
  email: {
    fontSize: 20,
    fontWeight: "700",
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 0.6,
    marginBottom: 8,
  },
  section: {
    borderRadius: 12,
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  sectionPlaceholder: {
    paddingVertical: 24,
    alignItems: "center",
    gap: 8,
  },
  placeholderText: {
    fontSize: 14,
    textAlign: "center",
  },
  retryText: {
    fontSize: 14,
    fontWeight: "600",
  },
  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    gap: 12,
  },
  settingLabel: {
    fontSize: 15,
    fontWeight: "500",
  },
  settingValue: {
    fontSize: 15,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
  },
  segmented: {
    flexDirection: "row",
    borderRadius: 8,
    padding: 2,
  },
  segment: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  segmentText: {
    fontSize: 13,
    fontWeight: "600",
  },
});
