import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
} from "react-native";

import { getColors } from "../lib/theme";

interface ListingResult {
  id: string;
  image_url: string;
  price: number | null;
  currency: string;
  platform: string;
  listing_url: string;
  similarity: number;
  confidence_label: string;
  title: string | null;
}

export default function ResultsScreen() {
  const params = useLocalSearchParams();
  const router = useRouter();
  const scheme = useColorScheme();
  const colors = getColors(scheme);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<ListingResult[]>([]);

  useEffect(() => {
    searchSimilar();
  }, []);

  const searchSimilar = async () => {
    setLoading(true);
    // TODO: Phase 4 — call /api/v1/search/find with image + bbox params
    setTimeout(() => {
      setResults([]);
      setLoading(false);
    }, 2000);
  };

  if (loading) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        {/* TODO: Phase 6 — skeleton/shimmer placeholders */}
        <View style={styles.skeletonGrid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <View
              key={i}
              style={[styles.skeletonCard, { backgroundColor: colors.skeleton }]}
            />
          ))}
        </View>
      </View>
    );
  }

  if (results.length === 0) {
    return (
      <View style={[styles.emptyContainer, { backgroundColor: colors.background }]}>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          No clothing found
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          Try uploading a different photo
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* TODO: Phase 4 — FlashList grid of ListingCard components */}
      {/* TODO: Phase 5 — PriceFilter bar for logged-in users */}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 8,
  },
  skeletonGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  skeletonCard: {
    width: "48%",
    aspectRatio: 0.75,
    borderRadius: 12,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 16,
  },
});
