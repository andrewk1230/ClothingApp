import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  LayoutChangeEvent,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import Svg from "react-native-svg";

import BoundingBoxOverlay from "../components/BoundingBoxOverlay";
import ManualCropTool, { ManualCropToolHandle } from "../components/ManualCropTool";
import { useAuth } from "../hooks/useAuth";
import { DetectedItem, useSearch } from "../hooks/useSearch";
import { useTheme } from "../hooks/useTheme";

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export default function SegmentationScreen() {
  const { imageUri, imageWidth, imageHeight } = useLocalSearchParams<{
    imageUri: string;
    imageWidth?: string;
    imageHeight?: string;
  }>();
  const router = useRouter();
  const { colors } = useTheme();
  const { isLoggedIn } = useAuth();
  const { segmentImage, items, segmentSize, segmenting, error } = useSearch();
  const [containerSize, setContainerSize] = useState<{ width: number; height: number } | null>(null);
  const [started, setStarted] = useState(false);
  const [cropMode, setCropMode] = useState(false);
  const cropRef = useRef<ManualCropToolHandle>(null);

  useEffect(() => {
    if (imageUri) {
      setStarted(true);
      segmentImage(imageUri);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUri]);

  const handleLayout = (event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    // Ignore transient zero-size layouts (e.g. mid modal presentation): a
    // zero container would yield scale=0 and divide-by-zero crop math.
    if (width > 0 && height > 0) {
      setContainerSize({ width, height });
    }
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

  const handleSearchWholeImage = () => {
    router.push({
      pathname: "/results",
      params: { imageUri },
    });
  };

  // Bbox coords are pixels in the backend-processed image (segmentSize).
  // Fall back to the compressed image dimensions passed via params — the
  // aspect ratio is identical, so scaling stays correct either way.
  const sourceWidth = segmentSize?.width ?? (imageWidth ? Number(imageWidth) : 0);
  const sourceHeight = segmentSize?.height ?? (imageHeight ? Number(imageHeight) : 0);

  // Compute the letterboxed display rect of the resizeMode="contain" image.
  let displayRect: { left: number; top: number; width: number; height: number; scale: number } | null = null;
  if (containerSize && sourceWidth > 0 && sourceHeight > 0) {
    const scale = Math.min(containerSize.width / sourceWidth, containerSize.height / sourceHeight);
    const width = sourceWidth * scale;
    const height = sourceHeight * scale;
    displayRect = {
      left: (containerSize.width - width) / 2,
      top: (containerSize.height - height) / 2,
      width,
      height,
      scale,
    };
  }

  const handleToggleCrop = () => {
    if (!isLoggedIn) {
      Alert.alert(
        "Sign in to use manual crop",
        "Manual crop lets you search any area of the photo.",
        [
          { text: "Not now", style: "cancel" },
          { text: "Sign In", onPress: () => router.push("/login") },
        ]
      );
      return;
    }
    setCropMode((value) => !value);
  };

  const handleSearchArea = () => {
    if (!displayRect || !cropRef.current) return;
    const rect = cropRef.current.getRect();

    // Inverse of the display transform: display points → backend pixels.
    const pxX = clampNumber(Math.round(rect.x / displayRect.scale), 0, sourceWidth - 1);
    const pxY = clampNumber(Math.round(rect.y / displayRect.scale), 0, sourceHeight - 1);
    const pxW = clampNumber(Math.round(rect.w / displayRect.scale), 1, sourceWidth - pxX);
    const pxH = clampNumber(Math.round(rect.h / displayRect.scale), 1, sourceHeight - pxY);

    // Manual crops intentionally send NO category param — the user framed an
    // arbitrary area, so visual similarity alone decides the results.
    router.push({
      pathname: "/results",
      params: {
        imageUri,
        bboxX: pxX.toString(),
        bboxY: pxY.toString(),
        bboxW: pxW.toString(),
        bboxH: pxH.toString(),
      },
    });
  };

  const showBoxes = !segmenting && !error && items.length > 0 && displayRect;
  const showEmpty = started && !segmenting && !error && items.length === 0;
  const isRateLimited = error?.type === "rate-limit";
  const cropAvailable = !!displayRect && !segmenting;

  const manualCropButton = cropAvailable ? (
    <TouchableOpacity
      style={[styles.secondaryButton, { borderColor: colors.border }]}
      onPress={handleToggleCrop}
    >
      <View style={styles.buttonRow}>
        {!isLoggedIn && (
          <Ionicons name="lock-closed" size={15} color={colors.textSecondary} />
        )}
        <Text style={[styles.secondaryButtonText, { color: colors.text }]}>
          Manual crop
        </Text>
      </View>
    </TouchableOpacity>
  ) : null;

  return (
    <GestureHandlerRootView style={[styles.container, { backgroundColor: colors.background }]}>
      {imageUri && (
        <View style={styles.imageContainer} onLayout={handleLayout}>
          <Image
            source={{ uri: imageUri }}
            style={[styles.image, segmenting && styles.imageDimmed]}
            resizeMode="contain"
          />
          {showBoxes && !cropMode && displayRect && (
            <Svg
              style={{
                position: "absolute",
                left: displayRect.left,
                top: displayRect.top,
              }}
              width={displayRect.width}
              height={displayRect.height}
            >
              {items.map((item) => (
                <BoundingBoxOverlay
                  key={item.id}
                  item={item}
                  scale={displayRect.scale}
                  displayWidth={displayRect.width}
                  strokeColor={colors.boxStroke}
                  chipColor={colors.chipBackground}
                  chipTextColor={colors.chipText}
                  onPress={() => handleItemTap(item)}
                />
              ))}
            </Svg>
          )}
          {cropMode && displayRect && (
            <View
              style={{
                position: "absolute",
                left: displayRect.left,
                top: displayRect.top,
                width: displayRect.width,
                height: displayRect.height,
              }}
              pointerEvents="box-none"
            >
              <ManualCropTool
                ref={cropRef}
                displayWidth={displayRect.width}
                displayHeight={displayRect.height}
                strokeColor={colors.boxStroke}
              />
            </View>
          )}
        </View>
      )}

      {segmenting && (
        <View style={[styles.loadingOverlay, { backgroundColor: colors.overlay }]}>
          <ActivityIndicator size="large" color="#FFFFFF" />
          <Text style={styles.loadingText}>Detecting items...</Text>
        </View>
      )}

      {cropMode && (
        <View style={[styles.bottomPanel, { backgroundColor: colors.background }]}>
          <Text style={[styles.panelText, { color: colors.textSecondary }]}>
            Drag to move. Pull the corners to resize.
          </Text>
          <TouchableOpacity
            style={[styles.primaryButton, { backgroundColor: colors.accent }]}
            onPress={handleSearchArea}
          >
            <Text style={[styles.primaryButtonText, { color: colors.accentText }]}>
              Search this area
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.secondaryButton, { borderColor: colors.border }]}
            onPress={() => setCropMode(false)}
          >
            <Text style={[styles.secondaryButtonText, { color: colors.text }]}>
              {items.length > 0 ? "Show detected items" : "Exit manual crop"}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {!cropMode && error && (
        <View style={[styles.bottomPanel, { backgroundColor: colors.background }]}>
          <Text style={[styles.panelText, { color: colors.error }]}>{error.message}</Text>
          {!isRateLimited && (
            <TouchableOpacity
              style={[styles.primaryButton, { backgroundColor: colors.accent }]}
              onPress={() => segmentImage(imageUri!)}
            >
              <Text style={[styles.primaryButtonText, { color: colors.accentText }]}>Retry</Text>
            </TouchableOpacity>
          )}
          {!isRateLimited && (
            <TouchableOpacity
              style={[styles.secondaryButton, { borderColor: colors.border }]}
              onPress={handleSearchWholeImage}
            >
              <Text style={[styles.secondaryButtonText, { color: colors.text }]}>
                Search entire image
              </Text>
            </TouchableOpacity>
          )}
          {!isRateLimited && manualCropButton}
        </View>
      )}

      {!cropMode && showEmpty && (
        <View style={[styles.bottomPanel, { backgroundColor: colors.background }]}>
          <Text style={[styles.panelTitle, { color: colors.text }]}>
            No clothing found
          </Text>
          <Text style={[styles.panelText, { color: colors.textSecondary }]}>
            We can still search using the whole photo.
          </Text>
          <TouchableOpacity
            style={[styles.primaryButton, { backgroundColor: colors.accent }]}
            onPress={handleSearchWholeImage}
          >
            <Text style={[styles.primaryButtonText, { color: colors.accentText }]}>
              Search entire image
            </Text>
          </TouchableOpacity>
          {manualCropButton}
        </View>
      )}

      {!cropMode && showBoxes && (
        <View style={[styles.bottomPanel, { backgroundColor: colors.background }]}>
          <Text style={[styles.panelText, { color: colors.textSecondary }]}>
            Tap an item to search, or use the whole photo.
          </Text>
          <TouchableOpacity
            style={[styles.secondaryButton, { borderColor: colors.border }]}
            onPress={handleSearchWholeImage}
          >
            <Text style={[styles.secondaryButtonText, { color: colors.text }]}>
              Search entire image
            </Text>
          </TouchableOpacity>
          {manualCropButton}
        </View>
      )}
    </GestureHandlerRootView>
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
  imageDimmed: {
    opacity: 0.4,
  },
  loadingOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: "#FFFFFF",
  },
  bottomPanel: {
    padding: 24,
    paddingBottom: 36,
    gap: 12,
    alignItems: "center",
  },
  panelTitle: {
    fontSize: 18,
    fontWeight: "700",
  },
  panelText: {
    fontSize: 15,
    textAlign: "center",
  },
  primaryButton: {
    alignSelf: "stretch",
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  secondaryButton: {
    alignSelf: "stretch",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
});
