import { FlashList } from "@shopify/flash-list";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import ListingCard from "../components/ListingCard";
import PriceFilterBar, { PriceFilters } from "../components/PriceFilterBar";
import { useAuth } from "../hooks/useAuth";
import { useSaved } from "../hooks/useSaved";
import { FindSimilarOptions, ListingResult, useSearch } from "../hooks/useSearch";
import { useTheme } from "../hooks/useTheme";
import api from "../lib/api";

/** Row shape returned by GET /api/v1/history/{id}/results. */
type HistoryResultRow = Omit<ListingResult, "similarity" | "confidence_label"> & {
  active: boolean;
};

function SkeletonGrid({ color }: { color: string }) {
  const pulse = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.5, duration: 700, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <View style={styles.skeletonGrid}>
      {Array.from({ length: 6 }).map((_, i) => (
        <Animated.View
          key={i}
          style={[styles.skeletonCard, { backgroundColor: color, opacity: pulse }]}
        />
      ))}
    </View>
  );
}

export default function ResultsScreen() {
  const params = useLocalSearchParams<{
    imageUri?: string;
    bboxX?: string;
    bboxY?: string;
    bboxW?: string;
    bboxH?: string;
    category?: string;
    historyId?: string;
  }>();
  const router = useRouter();
  const { colors } = useTheme();
  const { isLoggedIn } = useAuth();
  const { isSaved, toggleSave, refresh: refreshSaved } = useSaved();
  const { findSimilar, results, searching, error } = useSearch();
  const [filters, setFilters] = useState<PriceFilters>({});
  const [started, setStarted] = useState(false);

  // History replay mode: instead of running a fresh search, show the stored
  // results of a past search. The original photo isn't kept, so there is no
  // re-search or price filtering here.
  const isHistory = params.historyId != null;
  const [historyItems, setHistoryItems] = useState<ListingResult[] | null>(null);
  const [historyInactive, setHistoryInactive] = useState<Set<string>>(new Set());
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const fetchHistoryResults = useCallback(async () => {
    if (!params.historyId) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const response = await api.get(`/api/v1/history/${params.historyId}/results`);
      const rows: HistoryResultRow[] = response.data ?? [];
      setHistoryInactive(new Set(rows.filter((r) => !r.active).map((r) => r.id)));
      setHistoryItems(
        rows.map(({ active: _active, ...rest }) => ({
          ...rest,
          // Not stored per history entry; "match" renders without a badge.
          similarity: 0,
          confidence_label: "match",
        }))
      );
    } catch {
      setHistoryError("Couldn't load this search's results.");
    } finally {
      setHistoryLoading(false);
    }
  }, [params.historyId]);

  const runSearch = useCallback(
    (activeFilters?: PriceFilters) => {
      if (!params.imageUri) return;
      setStarted(true);

      const options: FindSimilarOptions = { ...(activeFilters ?? filters) };
      if (params.bboxX != null && params.bboxW != null) {
        const bbox = {
          x: Number(params.bboxX),
          y: Number(params.bboxY),
          w: Number(params.bboxW),
          h: Number(params.bboxH),
        };
        // Route params are strings; a malformed value would reach the backend
        // as "NaN" and fail validation. Fall back to a whole-image search.
        if ([bbox.x, bbox.y, bbox.w, bbox.h].every(Number.isFinite)) {
          options.bbox = bbox;
        }
      }
      if (params.category) options.category = params.category;

      findSimilar(params.imageUri, options);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [params.imageUri, params.bboxX, params.bboxY, params.bboxW, params.bboxH, params.category, filters]
  );

  useEffect(() => {
    if (isHistory) {
      fetchHistoryResults();
    } else {
      runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-sync hearts when returning from listing detail (or after signing in).
  useFocusEffect(
    useCallback(() => {
      refreshSaved();
    }, [refreshSaved])
  );

  const handleApplyFilters = (next: PriceFilters) => {
    setFilters(next);
    runSearch(next);
  };

  const handleSaveTap = (listing: ListingResult) => {
    if (!isLoggedIn) {
      Alert.alert(
        "Sign in to save items",
        "Create an account to build your wishlist.",
        [
          { text: "Not now", style: "cancel" },
          { text: "Sign In", onPress: () => router.push("/login") },
        ]
      );
      return;
    }
    toggleSave(listing.id);
  };

  const openListing = (listing: ListingResult) => {
    router.push({
      pathname: "/listing/[id]",
      params: { id: listing.id, listing: JSON.stringify(listing) },
    });
  };

  const hasActiveFilters = filters.minPrice != null || filters.maxPrice != null;

  const displayResults = isHistory ? historyItems ?? [] : results;
  const loading = isHistory
    ? historyLoading || (historyItems === null && !historyError)
    : searching || !started;

  let body: ReactNode;
  if (loading) {
    body = (
      <View style={styles.container}>
        <SkeletonGrid color={colors.skeleton} />
      </View>
    );
  } else if (isHistory && historyError) {
    body = (
      <View style={styles.emptyContainer}>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          Something went wrong
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          {historyError}
        </Text>
        <TouchableOpacity
          style={[styles.retryButton, { backgroundColor: colors.accent }]}
          onPress={fetchHistoryResults}
        >
          <Text style={[styles.retryButtonText, { color: colors.accentText }]}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  } else if (!isHistory && error) {
    body = (
      <View style={styles.emptyContainer}>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          {error.type === "rate-limit" ? "Search limit reached" : "Something went wrong"}
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          {error.message}
        </Text>
        {error.type !== "rate-limit" && (
          <TouchableOpacity
            style={[styles.retryButton, { backgroundColor: colors.accent }]}
            onPress={() => runSearch()}
          >
            <Text style={[styles.retryButtonText, { color: colors.accentText }]}>Retry</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  } else if (displayResults.length === 0) {
    body = (
      <View style={styles.emptyContainer}>
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          {isHistory ? "Nothing to show" : "No clothing found"}
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          {isHistory
            ? "The items from this search are no longer available"
            : hasActiveFilters
              ? "Try adjusting your price filters or uploading a different photo"
              : "Try uploading a different photo"}
        </Text>
      </View>
    );
  } else {
    body = (
      <FlashList
        data={displayResults}
        numColumns={2}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.cardWrapper}>
            <ListingCard
              listing={item}
              onPress={() => openListing(item)}
              onSave={() => handleSaveTap(item)}
              isSaved={isSaved(item.id)}
              inactive={isHistory && historyInactive.has(item.id)}
            />
          </View>
        )}
        contentContainerStyle={styles.listContent}
      />
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      {!isHistory && (
        <PriceFilterBar
          isLoggedIn={isLoggedIn}
          filters={filters}
          onApply={handleApplyFilters}
          onSignIn={() => router.push("/login")}
        />
      )}
      {body}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  container: {
    flex: 1,
    padding: 8,
  },
  listContent: {
    padding: 4,
  },
  cardWrapper: {
    flex: 1,
    padding: 4,
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
    textAlign: "center",
  },
  retryButton: {
    marginTop: 24,
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
  },
  retryButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
});
