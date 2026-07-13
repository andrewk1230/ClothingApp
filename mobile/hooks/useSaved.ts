import { useCallback, useEffect, useState } from "react";
import { Alert } from "react-native";

import api from "../lib/api";
import { useAuth } from "./useAuth";

interface SavedRecord {
  id: string;
  /** UUID of the row in the listings table — matches ListingResult.id. */
  listing_id: string;
  created_at: string;
  [key: string]: unknown;
}

export function useSaved() {
  const { isLoggedIn } = useAuth();
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!isLoggedIn) {
      setSavedIds(new Set());
      return;
    }
    setLoading(true);
    try {
      const response = await api.get("/api/v1/saved");
      const records: SavedRecord[] = response.data ?? [];
      setSavedIds(new Set(records.map((record) => record.listing_id)));
    } catch {
      // Best-effort: hearts simply render unsaved until the next successful fetch.
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggleSave = useCallback(
    async (listingId: string): Promise<boolean> => {
      if (!isLoggedIn) return false;
      const wasSaved = savedIds.has(listingId);

      // Optimistic update.
      setSavedIds((prev) => {
        const next = new Set(prev);
        if (wasSaved) {
          next.delete(listingId);
        } else {
          next.add(listingId);
        }
        return next;
      });

      try {
        if (wasSaved) {
          await api.delete(`/api/v1/saved/${listingId}`);
        } else {
          await api.post(`/api/v1/saved/${listingId}`);
        }
        return true;
      } catch {
        // Rollback and surface the failure.
        setSavedIds((prev) => {
          const next = new Set(prev);
          if (wasSaved) {
            next.add(listingId);
          } else {
            next.delete(listingId);
          }
          return next;
        });
        Alert.alert(
          "Couldn't update saved items",
          "Check your connection and try again."
        );
        return false;
      }
    },
    [isLoggedIn, savedIds]
  );

  const isSaved = useCallback(
    (listingId: string) => savedIds.has(listingId),
    [savedIds]
  );

  return { savedIds, isSaved, toggleSave, refresh, loading };
}
