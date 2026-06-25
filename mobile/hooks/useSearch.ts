import { useState } from "react";

import api from "../lib/api";

interface DetectedItem {
  id: string;
  bbox: { x: number; y: number; w: number; h: number };
  category: string;
  confidence: number;
}

interface ListingResult {
  id: string;
  image_url: string;
  price: number | null;
  currency: string;
  platform: string;
  listing_url: string;
  similarity: number;
  confidence_label: string;
  title: string | null;
}

export function useSearch() {
  const [segmenting, setSegmenting] = useState(false);
  const [searching, setSearching] = useState(false);
  const [items, setItems] = useState<DetectedItem[]>([]);
  const [results, setResults] = useState<ListingResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const segmentImage = async (imageUri: string) => {
    setSegmenting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("image", {
        uri: imageUri,
        type: "image/jpeg",
        name: "photo.jpg",
      } as any);

      const response = await api.post("/api/v1/search/segment", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setItems(response.data.items);
    } catch (e: any) {
      setError(e.message || "Failed to analyze image");
    } finally {
      setSegmenting(false);
    }
  };

  const findSimilar = async (
    imageUri: string,
    bbox: { x: number; y: number; w: number; h: number },
    filters?: { minPrice?: number; maxPrice?: number }
  ) => {
    setSearching(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("image", {
        uri: imageUri,
        type: "image/jpeg",
        name: "photo.jpg",
      } as any);

      const params = new URLSearchParams();
      params.append("bbox_x", bbox.x.toString());
      params.append("bbox_y", bbox.y.toString());
      params.append("bbox_w", bbox.w.toString());
      params.append("bbox_h", bbox.h.toString());
      if (filters?.minPrice != null) params.append("min_price", filters.minPrice.toString());
      if (filters?.maxPrice != null) params.append("max_price", filters.maxPrice.toString());

      const response = await api.post(
        `/api/v1/search/find?${params.toString()}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setResults(response.data.results);
    } catch (e: any) {
      setError(e.message || "Search failed");
    } finally {
      setSearching(false);
    }
  };

  return { segmentImage, findSimilar, items, results, segmenting, searching, error };
}
