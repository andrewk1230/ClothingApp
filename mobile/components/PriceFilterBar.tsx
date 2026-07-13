import { Ionicons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { useTheme } from "../hooks/useTheme";

export interface PriceFilters {
  minPrice?: number;
  maxPrice?: number;
}

interface PriceFilterBarProps {
  isLoggedIn: boolean;
  filters: PriceFilters;
  onApply: (filters: PriceFilters) => void;
  onSignIn: () => void;
}

const PRESETS: { label: string; filters: PriceFilters }[] = [
  { label: "Under $25", filters: { maxPrice: 25 } },
  { label: "$25-50", filters: { minPrice: 25, maxPrice: 50 } },
  { label: "$50-100", filters: { minPrice: 50, maxPrice: 100 } },
  { label: "$100+", filters: { minPrice: 100 } },
];

function parsePrice(text: string): number | undefined {
  const cleaned = text.trim().replace(/[^0-9.]/g, "");
  // A cleaned-out string (e.g. "abc" -> "") must NOT become Number("") === 0;
  // returning undefined lets the caller surface a validation error instead.
  if (cleaned === "") return undefined;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : undefined;
}

export default function PriceFilterBar({
  isLoggedIn,
  filters,
  onApply,
  onSignIn,
}: PriceFilterBarProps) {
  const { colors } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [minText, setMinText] = useState("");
  const [maxText, setMaxText] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Keep the inputs in sync when filters change externally (presets, chip clears).
  useEffect(() => {
    setMinText(filters.minPrice != null ? String(filters.minPrice) : "");
    setMaxText(filters.maxPrice != null ? String(filters.maxPrice) : "");
  }, [filters.minPrice, filters.maxPrice]);

  if (!isLoggedIn) {
    return (
      <TouchableOpacity
        style={[
          styles.guestBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.border },
        ]}
        onPress={onSignIn}
        activeOpacity={0.7}
      >
        <Ionicons name="lock-closed" size={14} color={colors.textSecondary} />
        <Text style={[styles.guestText, { color: colors.textSecondary }]}>
          Sign in to filter by price
        </Text>
      </TouchableOpacity>
    );
  }

  const handleApply = () => {
    const min = parsePrice(minText);
    const max = parsePrice(maxText);
    if (
      (minText.trim() !== "" && min == null) ||
      (maxText.trim() !== "" && max == null)
    ) {
      setValidationError("Enter valid prices.");
      return;
    }
    if (min != null && max != null && min > max) {
      setValidationError("Min price can't exceed max price.");
      return;
    }
    setValidationError(null);
    setExpanded(false);
    onApply({ minPrice: min, maxPrice: max });
  };

  const handlePreset = (preset: PriceFilters) => {
    setValidationError(null);
    setExpanded(false);
    onApply(preset);
  };

  const clearMin = () => onApply({ maxPrice: filters.maxPrice });
  const clearMax = () => onApply({ minPrice: filters.minPrice });

  return (
    <View style={[styles.container, { borderBottomColor: colors.border }]}>
      <View style={styles.topRow}>
        <TouchableOpacity
          style={[styles.filterToggle, { borderColor: colors.border }]}
          onPress={() => {
            setValidationError(null);
            setExpanded((value) => !value);
          }}
        >
          <Ionicons name="funnel-outline" size={14} color={colors.text} />
          <Text style={[styles.filterToggleText, { color: colors.text }]}>Price</Text>
          <Ionicons
            name={expanded ? "chevron-up" : "chevron-down"}
            size={14}
            color={colors.textSecondary}
          />
        </TouchableOpacity>

        {filters.minPrice != null && (
          <View style={[styles.chip, { backgroundColor: colors.accent }]}>
            <Text style={[styles.chipText, { color: colors.accentText }]}>
              Min ${filters.minPrice}
            </Text>
            <TouchableOpacity onPress={clearMin} hitSlop={8}>
              <Ionicons name="close" size={14} color={colors.accentText} />
            </TouchableOpacity>
          </View>
        )}
        {filters.maxPrice != null && (
          <View style={[styles.chip, { backgroundColor: colors.accent }]}>
            <Text style={[styles.chipText, { color: colors.accentText }]}>
              Max ${filters.maxPrice}
            </Text>
            <TouchableOpacity onPress={clearMax} hitSlop={8}>
              <Ionicons name="close" size={14} color={colors.accentText} />
            </TouchableOpacity>
          </View>
        )}
      </View>

      {expanded && (
        <View style={styles.panel}>
          <View style={styles.inputRow}>
            <TextInput
              style={[
                styles.input,
                { borderColor: colors.border, color: colors.text },
              ]}
              value={minText}
              onChangeText={setMinText}
              placeholder="Min $"
              placeholderTextColor={colors.textSecondary}
              keyboardType="decimal-pad"
              returnKeyType="done"
            />
            <Text style={[styles.inputSeparator, { color: colors.textSecondary }]}>
              to
            </Text>
            <TextInput
              style={[
                styles.input,
                { borderColor: colors.border, color: colors.text },
              ]}
              value={maxText}
              onChangeText={setMaxText}
              placeholder="Max $"
              placeholderTextColor={colors.textSecondary}
              keyboardType="decimal-pad"
              returnKeyType="done"
            />
            <TouchableOpacity
              style={[styles.applyButton, { backgroundColor: colors.accent }]}
              onPress={handleApply}
            >
              <Text style={[styles.applyButtonText, { color: colors.accentText }]}>
                Apply
              </Text>
            </TouchableOpacity>
          </View>

          {validationError && (
            <Text style={[styles.errorText, { color: colors.error }]}>
              {validationError}
            </Text>
          )}

          <View style={styles.presetRow}>
            {PRESETS.map((preset) => (
              <TouchableOpacity
                key={preset.label}
                style={[
                  styles.presetChip,
                  { borderColor: colors.border, backgroundColor: colors.surface },
                ]}
                onPress={() => handlePreset(preset.filters)}
              >
                <Text style={[styles.presetChipText, { color: colors.text }]}>
                  {preset.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 8,
  },
  guestBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  guestText: {
    fontSize: 13,
    fontWeight: "500",
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  filterToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  filterToggleText: {
    fontSize: 13,
    fontWeight: "600",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
  },
  chipText: {
    fontSize: 13,
    fontWeight: "600",
  },
  panel: {
    gap: 8,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
  },
  inputSeparator: {
    fontSize: 13,
  },
  applyButton: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 8,
  },
  applyButtonText: {
    fontSize: 14,
    fontWeight: "600",
  },
  errorText: {
    fontSize: 13,
  },
  presetRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  presetChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  presetChipText: {
    fontSize: 13,
    fontWeight: "500",
  },
});
