import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Linking from "expo-linking";
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { formatPrice } from "../../components/ListingCard";
import { useAuth } from "../../hooks/useAuth";
import { useSaved } from "../../hooks/useSaved";
import { ListingResult } from "../../hooks/useSearch";
import api from "../../lib/api";
import { useTheme } from "../../hooks/useTheme";

export default function ListingDetailScreen() {
  const { id, listing: listingParam } = useLocalSearchParams<{
    id: string;
    listing?: string;
  }>();
  const router = useRouter();
  const { colors } = useTheme();
  const { isLoggedIn } = useAuth();
  const { isSaved, toggleSave } = useSaved();
  const [isActive, setIsActive] = useState(true);
  const [linkError, setLinkError] = useState<string | null>(null);

  const listing = useMemo<ListingResult | null>(() => {
    if (!listingParam) return null;
    try {
      return JSON.parse(listingParam) as ListingResult;
    } catch {
      return null;
    }
  }, [listingParam]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api
      .get(`/api/v1/listings/${id}/check`)
      .then((response) => {
        if (cancelled) return;
        const active = response.data?.active ?? response.data?.is_active;
        if (active === false) setIsActive(false);
      })
      .catch(() => {
        // Availability check is best-effort; keep the listing usable on failure.
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const handleViewListing = async () => {
    if (!listing) return;
    setLinkError(null);
    try {
      await Linking.openURL(listing.listing_url);
    } catch {
      setLinkError("Couldn't open the listing. Please try again later.");
    }
  };

  const handleToggleSave = () => {
    if (!listing) return;
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

  if (!listing) {
    return (
      <View style={[styles.fallbackContainer, { backgroundColor: colors.background }]}>
        <Text style={[styles.fallbackText, { color: colors.textSecondary }]}>
          Listing details unavailable. Go back and try again.
        </Text>
      </View>
    );
  }

  const isEbay = listing.platform.toLowerCase() === "ebay";
  const platformName = isEbay ? "eBay" : listing.platform;

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.content}
    >
      {!isActive && (
        <View style={[styles.banner, { backgroundColor: colors.warningSurface }]}>
          <Text style={[styles.bannerText, { color: colors.warning }]}>
            This listing is no longer available
          </Text>
        </View>
      )}

      <Image source={{ uri: listing.image_url }} style={styles.image} resizeMode="cover" />

      <View style={styles.details}>
        {listing.title != null && (
          <Text style={[styles.title, { color: colors.text }]}>{listing.title}</Text>
        )}
        <Text style={[styles.price, { color: colors.text }]}>
          {formatPrice(listing.price, listing.currency)}
        </Text>

        <View style={styles.metaRows}>
          {listing.size != null && (
            <View style={styles.metaRow}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Size</Text>
              <Text style={[styles.metaValue, { color: colors.text }]}>{listing.size}</Text>
            </View>
          )}
          {listing.condition != null && (
            <View style={styles.metaRow}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Condition</Text>
              <Text style={[styles.metaValue, { color: colors.text }]}>{listing.condition}</Text>
            </View>
          )}
          <View style={styles.metaRow}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Platform</Text>
            <Text style={[styles.metaValue, { color: colors.text }]}>{platformName}</Text>
          </View>
        </View>

        <View style={styles.ctaRow}>
          <TouchableOpacity
            style={[
              styles.ctaButton,
              { backgroundColor: colors.accent },
              !isActive && styles.ctaDisabled,
            ]}
            onPress={handleViewListing}
            disabled={!isActive}
          >
            <Text style={[styles.ctaText, { color: colors.accentText }]}>
              View on {platformName}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.saveButton, { borderColor: colors.border }]}
            onPress={handleToggleSave}
            accessibilityLabel={
              isSaved(listing.id) ? "Remove from saved items" : "Save item"
            }
          >
            <Ionicons
              name={isSaved(listing.id) ? "heart" : "heart-outline"}
              size={24}
              color={isSaved(listing.id) ? colors.error : colors.text}
            />
          </TouchableOpacity>
        </View>

        {linkError && (
          <Text style={[styles.linkError, { color: colors.error }]}>{linkError}</Text>
        )}

        {isEbay && (
          <Text style={[styles.disclosure, { color: colors.textSecondary }]}>
            Listing details and prices are provided by eBay. GrailSeeker is not
            affiliated with or endorsed by eBay Inc.
          </Text>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    paddingBottom: 48,
  },
  banner: {
    padding: 12,
    alignItems: "center",
  },
  bannerText: {
    fontSize: 14,
    fontWeight: "600",
  },
  image: {
    width: "100%",
    aspectRatio: 3 / 4,
  },
  details: {
    padding: 16,
    gap: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: "600",
  },
  price: {
    fontSize: 24,
    fontWeight: "700",
  },
  metaRows: {
    marginTop: 8,
    gap: 8,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  metaLabel: {
    fontSize: 15,
  },
  metaValue: {
    fontSize: 15,
    fontWeight: "500",
  },
  ctaRow: {
    marginTop: 24,
    flexDirection: "row",
    alignItems: "stretch",
    gap: 12,
  },
  ctaButton: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  saveButton: {
    width: 56,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaDisabled: {
    opacity: 0.4,
  },
  ctaText: {
    fontSize: 16,
    fontWeight: "600",
  },
  linkError: {
    marginTop: 8,
    fontSize: 14,
    textAlign: "center",
  },
  disclosure: {
    marginTop: 16,
    fontSize: 12,
    lineHeight: 17,
    textAlign: "center",
  },
  fallbackContainer: {
    flex: 1,
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  fallbackText: {
    fontSize: 16,
    textAlign: "center",
  },
});
