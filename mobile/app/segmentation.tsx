import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
} from "react-native";

import { getColors } from "../lib/theme";

interface DetectedItem {
  id: string;
  bbox: { x: number; y: number; w: number; h: number };
  category: string;
  confidence: number;
}

export default function SegmentationScreen() {
  const { imageUri } = useLocalSearchParams<{ imageUri: string }>();
  const router = useRouter();
  const scheme = useColorScheme();
  const colors = getColors(scheme);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<DetectedItem[]>([]);

  useEffect(() => {
    if (imageUri) {
      segmentImage();
    }
  }, [imageUri]);

  const segmentImage = async () => {
    setLoading(true);
    // TODO: Phase 4 — call /api/v1/search/segment with uploaded image
    // For now, simulate a delay
    setTimeout(() => {
      setItems([]);
      setLoading(false);
    }, 1000);
  };

  const handleItemTap = (item: DetectedItem) => {
    router.push({
      pathname: "/results",
      params: {
        imageUri,
        bboxX: item.bbox.x.toString(),
        bboxY: item.bbox.y.toString(),
        bboxW: item.bbox.w.toString(),
        bboxH: item.bbox.h.toString(),
        category: item.category,
      },
    });
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {imageUri && (
        <View style={styles.imageContainer}>
          <Image source={{ uri: imageUri }} style={styles.image} resizeMode="contain" />
          {/* TODO: Phase 4 — render bounding box overlays with react-native-svg */}
          {/* TODO: Phase 5 — render ManualCropTool for logged-in users */}
        </View>
      )}

      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.textSecondary }]}>
            Detecting clothing items...
          </Text>
        </View>
      )}

      {!loading && items.length === 0 && (
        <View style={styles.emptyState}>
          <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
            No clothing items detected. Try a clearer photo.
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  imageContainer: {
    flex: 1,
    position: "relative",
  },
  image: {
    flex: 1,
    width: "100%",
  },
  loadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.3)",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
  },
  emptyState: {
    position: "absolute",
    bottom: 48,
    left: 24,
    right: 24,
    alignItems: "center",
  },
  emptyText: {
    fontSize: 16,
    textAlign: "center",
  },
});
