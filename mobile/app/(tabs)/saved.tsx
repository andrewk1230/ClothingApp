import { FlashList } from "@shopify/flash-list";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import ListingCard from "../../components/ListingCard";
import { useAuth } from "../../hooks/useAuth";
import { ListingResult } from "../../hooks/useSearch";
import { useTheme } from "../../hooks/useTheme";
import api from "../../lib/api";

interface SavedItem {
  id: string;
  listing_id: string;
  image_url: string;
  price: number | null;
  currency: string;
  size: string | null;
  condition: string | null;
  title: string | null;
  platform: string;
  listing_url: string;
  created_at: string;
}

function toCardShape(item: SavedItem): ListingResult {
  return {
    id: item.listing_id,
    image_url: item.image_url,
    price: item.price,
    currency: item.currency,
    size: item.size,
    condition: item.condition,
    title: item.title,
    platform: item.platform,
    listing_url: item.listing_url,
    similarity: 1,
    confidence_label: "match",
  };
}

const SKELETON_COUNT = 6;

export default function SavedScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const { isLoggedIn, loading: authLoading } = useAuth();

  const [items, setItems] = useState<SavedItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unsaveError, setUnsaveError] = useState<string | null>(null);

  const fetchSaved = useCallback(
    async (asRefresh: boolean) => {
      if (asRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const response = await api.get("/api/v1/saved");
        setItems(response.data ?? []);
      } catch {
        setError("Couldn't load your saved items.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  useFocusEffect(
    useCallback(() => {
      if (isLoggedIn) {
        fetchSaved(false);
      }
    }, [isLoggedIn, fetchSaved])
  );

  const handleUnsave = useCallback(
    (listingId: string) => {
      setUnsaveError(null);
      let previous: SavedItem[] | null = null;
      setItems((current) => {
        previous = current;
        return current
          ? current.filter((item) => item.listing_id !== listingId)
          : current;
      });
      api.delete(`/api/v1/saved/${listingId}`).catch(() => {
        // Roll back the optimistic removal.
        setItems(previous);
        setUnsaveError("Couldn't remove that item. Please try again.");
      });
    },
    []
  );

  const handlePress = useCallback(
    (item: SavedItem) => {
      const cardShape = toCardShape(item);
      router.push({
        pathname: "/listing/[id]",
        params: {
          id: item.listing_id,
          listing: JSON.stringify(cardShape),
        },
      });
    },
    [router]
  );

  if (authLoading) {
    return (
      <View
        style={[styles.centered, { backgroundColor: colors.background }]}
      />
    );
  }

  if (!isLoggedIn) {
    return (
      <View style={[styles.centered, { backgroundColor: colors.background }]}>
        <Text style={[styles.gateTitle, { color: colors.text }]}>
          Saved Items
        </Text>
        <Text style={[styles.gateSubtitle, { color: colors.textSecondary }]}>
          Sign in to save items to your wishlist
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

  if (loading && items === null) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.skeletonGrid}>
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <View key={i} style={styles.skeletonCell}>
              <View
                style={[styles.skeletonImage, { backgroundColor: colors.skeleton }]}
              />
              <View
                style={[styles.skeletonLine, { backgroundColor: colors.skeleton }]}
              />
            </View>
          ))}
        </View>
      </View>
    );
  }

  if (error && (items === null || items.length === 0)) {
    return (
      <View style={[styles.centered, { backgroundColor: colors.background }]}>
        <Text style={[styles.gateSubtitle, { color: colors.textSecondary }]}>
          {error}
        </Text>
        <TouchableOpacity
          style={[styles.gateButton, { backgroundColor: colors.accent }]}
          onPress={() => fetchSaved(false)}
        >
          <Text style={[styles.gateButtonText, { color: colors.accentText }]}>
            Retry
          </Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (items !== null && items.length === 0) {
    return (
      <View style={[styles.centered, { backgroundColor: colors.background }]}>
        <Text style={[styles.gateTitle, { color: colors.text }]}>
          Nothing saved yet
        </Text>
        <Text style={[styles.gateSubtitle, { color: colors.textSecondary }]}>
          Nothing saved yet — tap the heart on a result
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {unsaveError && (
        <View style={[styles.banner, { backgroundColor: colors.warningSurface }]}>
          <Text style={[styles.bannerText, { color: colors.warning }]}>
            {unsaveError}
          </Text>
        </View>
      )}
      <FlashList
        data={items ?? []}
        numColumns={2}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        onRefresh={() => fetchSaved(true)}
        refreshing={refreshing}
        renderItem={({ item }) => (
          <View style={styles.cardCell}>
            <ListingCard
              listing={toCardShape(item)}
              onPress={() => handlePress(item)}
              onSave={() => handleUnsave(item.listing_id)}
              isSaved
            />
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
  listContent: {
    padding: 8,
  },
  cardCell: {
    flex: 1,
    padding: 8,
  },
  skeletonGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    padding: 8,
  },
  skeletonCell: {
    width: "50%",
    padding: 8,
  },
  skeletonImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 12,
  },
  skeletonLine: {
    marginTop: 10,
    height: 14,
    width: "60%",
    borderRadius: 7,
  },
  banner: {
    padding: 10,
    alignItems: "center",
  },
  bannerText: {
    fontSize: 13,
    fontWeight: "600",
  },
});
