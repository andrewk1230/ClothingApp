import { useLocalSearchParams } from "expo-router";
import * as Linking from "expo-linking";
import {
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
} from "react-native";

import { getColors } from "../../lib/theme";

export default function ListingDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const scheme = useColorScheme();
  const colors = getColors(scheme);

  // TODO: Phase 4 — fetch listing details from backend or pass via params

  const handleViewListing = (url: string) => {
    Linking.openURL(url);
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* TODO: Phase 4 — full listing detail view */}
      <Text style={[styles.placeholder, { color: colors.textSecondary }]}>
        Listing detail for {id}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  placeholder: {
    fontSize: 16,
    textAlign: "center",
    marginTop: 48,
  },
});
