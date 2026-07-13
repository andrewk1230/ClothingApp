import { useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { IMAGE_COMPRESSION_QUALITY, IMAGE_MAX_DIMENSION } from "../../constants/config";
import { useTheme } from "../../hooks/useTheme";

export default function HomeScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const [processing, setProcessing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const compressAndNavigate = async (asset: ImagePicker.ImagePickerAsset) => {
    setProcessing(true);
    try {
      const context = ImageManipulator.manipulate(asset.uri);
      if (Math.max(asset.width, asset.height) > IMAGE_MAX_DIMENSION) {
        if (asset.width >= asset.height) {
          context.resize({ width: IMAGE_MAX_DIMENSION });
        } else {
          context.resize({ height: IMAGE_MAX_DIMENSION });
        }
      }
      const rendered = await context.renderAsync();
      const result = await rendered.saveAsync({
        format: SaveFormat.JPEG,
        compress: IMAGE_COMPRESSION_QUALITY,
      });

      router.push({
        pathname: "/segmentation",
        params: {
          imageUri: result.uri,
          imageWidth: result.width.toString(),
          imageHeight: result.height.toString(),
        },
      });
    } catch {
      setMessage("Couldn't process that photo. Please try another one.");
    } finally {
      setProcessing(false);
    }
  };

  const pickImage = async () => {
    setMessage(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 1,
      });
      if (!result.canceled && result.assets[0]) {
        await compressAndNavigate(result.assets[0]);
      }
    } catch {
      setMessage("Couldn't open your photo library. Check GrailSeeker's photo access in Settings.");
    }
  };

  const takePhoto = async () => {
    setMessage(null);
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      setMessage("Camera access is required to take a photo. Enable it for GrailSeeker in Settings.");
      return;
    }

    try {
      const result = await ImagePicker.launchCameraAsync({
        quality: 1,
      });
      if (!result.canceled && result.assets[0]) {
        await compressAndNavigate(result.assets[0]);
      }
    } catch {
      setMessage("Couldn't open the camera. Please try again.");
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Text style={[styles.title, { color: colors.text }]}>GrailSeeker</Text>
      <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
        Upload a photo to find similar clothing
      </Text>

      <View style={styles.buttonGroup}>
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.accent }, processing && styles.disabled]}
          onPress={takePhoto}
          disabled={processing}
        >
          <Text style={[styles.buttonText, { color: colors.accentText }]}>
            Take Photo
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.button,
            {
              backgroundColor: colors.background,
              borderWidth: 1,
              borderColor: colors.border,
            },
            processing && styles.disabled,
          ]}
          onPress={pickImage}
          disabled={processing}
        >
          <Text style={[styles.buttonText, { color: colors.text }]}>
            Choose from Library
          </Text>
        </TouchableOpacity>
      </View>

      {processing && (
        <View style={styles.statusRow}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={[styles.statusText, { color: colors.textSecondary }]}>
            Preparing photo...
          </Text>
        </View>
      )}

      {message && (
        <Text style={[styles.message, { color: colors.error }]}>{message}</Text>
      )}
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
    fontSize: 32,
    fontWeight: "700",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    marginBottom: 48,
    textAlign: "center",
  },
  buttonGroup: {
    width: "100%",
    gap: 12,
  },
  button: {
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
  },
  buttonText: {
    fontSize: 16,
    fontWeight: "600",
  },
  disabled: {
    opacity: 0.5,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 24,
  },
  statusText: {
    fontSize: 14,
  },
  message: {
    fontSize: 14,
    textAlign: "center",
    marginTop: 24,
  },
});
