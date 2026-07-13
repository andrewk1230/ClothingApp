import { Ionicons } from "@expo/vector-icons";
import { Image, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { useTheme } from "../hooks/useTheme";

export interface HistoryEntry {
  id: string;
  category: string | null;
  bbox: { x: number; y: number; w: number; h: number } | null;
  result_count: number;
  thumbnail_urls: string[];
  created_at: string;
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "Just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  return new Date(iso).toLocaleDateString();
}

function categoryLabel(category: string | null): string {
  if (!category) return "Full image";
  return category.charAt(0).toUpperCase() + category.slice(1);
}

interface HistoryRowProps {
  entry: HistoryEntry;
  onDelete: () => void;
}

export default function HistoryRow({ entry, onDelete }: HistoryRowProps) {
  const { colors } = useTheme();
  const thumbnails = entry.thumbnail_urls.slice(0, 3);

  return (
    <View style={[styles.row, { borderBottomColor: colors.border }]}>
      <View style={styles.thumbnails}>
        {thumbnails.length > 0 ? (
          thumbnails.map((url, i) => (
            <Image
              key={`${url}-${i}`}
              source={{ uri: url }}
              style={[styles.thumbnail, { backgroundColor: colors.skeleton }]}
            />
          ))
        ) : (
          <View style={[styles.thumbnail, { backgroundColor: colors.skeleton }]} />
        )}
      </View>
      <View style={styles.info}>
        <Text style={[styles.category, { color: colors.text }]} numberOfLines={1}>
          {categoryLabel(entry.category)}
        </Text>
        <Text style={[styles.meta, { color: colors.textSecondary }]}>
          {entry.result_count} {entry.result_count === 1 ? "result" : "results"}
          {" · "}
          {formatRelativeTime(entry.created_at)}
        </Text>
      </View>
      <TouchableOpacity
        onPress={onDelete}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        style={styles.deleteButton}
      >
        <Ionicons name="trash-outline" size={20} color={colors.textSecondary} />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  thumbnails: {
    flexDirection: "row",
    gap: 4,
  },
  thumbnail: {
    width: 40,
    height: 40,
    borderRadius: 6,
  },
  info: {
    flex: 1,
    gap: 2,
  },
  category: {
    fontSize: 15,
    fontWeight: "600",
  },
  meta: {
    fontSize: 13,
  },
  deleteButton: {
    padding: 4,
  },
});
