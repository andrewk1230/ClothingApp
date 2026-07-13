import { Ionicons } from "@expo/vector-icons";
import {
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { ListingResult } from "../hooks/useSearch";
import { useTheme } from "../hooks/useTheme";

interface ListingCardProps {
  listing: ListingResult;
  onPress: () => void;
  /** Tapped on the heart overlay; the heart renders only when provided. */
  onSave?: () => void;
  isSaved?: boolean;
}

export function formatPrice(price: number | null, currency: string): string {
  if (price == null) return "Price unavailable";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
    }).format(price);
  } catch {
    return `${currency} ${price.toFixed(2)}`;
  }
}

function platformLabel(platform: string): string {
  if (platform.toLowerCase() === "ebay") return "eBay";
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}

export default function ListingCard({ listing, onPress, onSave, isSaved }: ListingCardProps) {
  const { colors } = useTheme();
  const isEbay = listing.platform.toLowerCase() === "ebay";

  return (
    <TouchableOpacity
      style={[styles.card, { backgroundColor: colors.surface }]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <View style={styles.imageWrapper}>
        <Image source={{ uri: listing.image_url }} style={styles.image} resizeMode="cover" />
        <View
          style={[
            styles.platformBadge,
            { backgroundColor: isEbay ? colors.badge.ebay : colors.accent },
          ]}
        >
          <Text style={styles.platformBadgeText}>{platformLabel(listing.platform)}</Text>
        </View>
        {listing.confidence_label === "similar" && (
          <View style={[styles.similarBadge, { backgroundColor: colors.chipBackground }]}>
            <Text style={[styles.similarBadgeText, { color: colors.chipText }]}>
              Similar match
            </Text>
          </View>
        )}
        {onSave && (
          <TouchableOpacity
            style={[styles.heartButton, { backgroundColor: colors.chipBackground }]}
            onPress={onSave}
            hitSlop={8}
            accessibilityLabel={isSaved ? "Remove from saved items" : "Save item"}
          >
            <Ionicons
              name={isSaved ? "heart" : "heart-outline"}
              size={18}
              color={isSaved ? "#F87171" : "#FFFFFF"}
            />
          </TouchableOpacity>
        )}
      </View>
      <View style={styles.info}>
        {listing.title != null && (
          <Text style={[styles.title, { color: colors.textSecondary }]} numberOfLines={1}>
            {listing.title}
          </Text>
        )}
        <Text style={[styles.price, { color: colors.text }]}>
          {formatPrice(listing.price, listing.currency)}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    borderRadius: 12,
    overflow: "hidden",
  },
  imageWrapper: {
    position: "relative",
  },
  image: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 12,
  },
  platformBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  platformBadgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  similarBadge: {
    position: "absolute",
    bottom: 8,
    left: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  similarBadgeText: {
    fontSize: 11,
    fontWeight: "600",
  },
  heartButton: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  info: {
    padding: 10,
    gap: 2,
  },
  title: {
    fontSize: 13,
  },
  price: {
    fontSize: 15,
    fontWeight: "700",
  },
});
