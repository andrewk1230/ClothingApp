import { isAxiosError } from "axios";
import { useRef, useState } from "react";

import api from "../lib/api";

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DetectedItem {
  id: string;
  bbox: BoundingBox;
  category: string;
  confidence: number;
}

export interface SegmentData {
  items: DetectedItem[];
  imageWidth: number;
  imageHeight: number;
}

export interface ListingResult {
  id: string;
  image_url: string;
  price: number | null;
  currency: string;
  size: string | null;
  condition: string | null;
  platform: string;
  listing_url: string;
  similarity: number;
  confidence_label: string;
  title: string | null;
}

export type SearchErrorType = "rate-limit" | "network" | "other";

export interface SearchError {
  type: SearchErrorType;
  message: string;
}

export interface FindSimilarOptions {
  bbox?: BoundingBox;
  category?: string;
  minPrice?: number;
  maxPrice?: number;
}

function toSearchError(e: unknown, fallback: string): SearchError {
  if (isAxiosError(e)) {
    if (e.response) {
      const detail = e.response.data?.detail;
      if (e.response.status === 429) {
        return {
          type: "rate-limit",
          message: typeof detail === "string" ? detail : "Daily search limit reached. Try again tomorrow.",
        };
      }
      return {
        type: "other",
        message: typeof detail === "string" ? detail : fallback,
      };
    }
    return { type: "network", message: "Check your connection and try again." };
  }
  return { type: "other", message: e instanceof Error ? e.message : fallback };
}

function buildImageFormData(imageUri: string): FormData {
  const formData = new FormData();
  formData.append("image", {
    uri: imageUri,
    type: "image/jpeg",
    name: "photo.jpg",
  } as any);
  return formData;
}

export function useSearch() {
  const [segmenting, setSegmenting] = useState(false);
  const [searching, setSearching] = useState(false);
  const [items, setItems] = useState<DetectedItem[]>([]);
  const [segmentSize, setSegmentSize] = useState<{ width: number; height: number } | null>(null);
  const [results, setResults] = useState<ListingResult[]>([]);
  const [error, setError] = useState<SearchError | null>(null);
  // Guards against out-of-order responses when a newer request is started
  // while an older one is still in flight (e.g. re-applying filters quickly):
  // only the latest request may touch state.
  const segmentSeq = useRef(0);
  const findSeq = useRef(0);

  const segmentImage = async (imageUri: string): Promise<SegmentData | null> => {
    const seq = ++segmentSeq.current;
    setSegmenting(true);
    setError(null);
    try {
      const response = await api.post("/api/v1/search/segment", buildImageFormData(imageUri), {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const data: SegmentData = {
        items: response.data.items ?? [],
        imageWidth: response.data.image_width,
        imageHeight: response.data.image_height,
      };
      if (seq === segmentSeq.current) {
        setItems(data.items);
        setSegmentSize({ width: data.imageWidth, height: data.imageHeight });
      }
      return data;
    } catch (e) {
      if (seq === segmentSeq.current) {
        setError(toSearchError(e, "Failed to analyze image"));
      }
      return null;
    } finally {
      if (seq === segmentSeq.current) {
        setSegmenting(false);
      }
    }
  };

  const findSimilar = async (
    imageUri: string,
    options: FindSimilarOptions = {}
  ): Promise<ListingResult[] | null> => {
    const seq = ++findSeq.current;
    setSearching(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (options.bbox) {
        params.append("bbox_x", options.bbox.x.toString());
        params.append("bbox_y", options.bbox.y.toString());
        params.append("bbox_w", options.bbox.w.toString());
        params.append("bbox_h", options.bbox.h.toString());
      }
      if (options.category) params.append("category", options.category);
      if (options.minPrice != null) params.append("min_price", options.minPrice.toString());
      if (options.maxPrice != null) params.append("max_price", options.maxPrice.toString());

      const query = params.toString();
      const response = await api.post(
        `/api/v1/search/find${query ? `?${query}` : ""}`,
        buildImageFormData(imageUri),
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      const found: ListingResult[] = response.data.results ?? [];
      if (seq === findSeq.current) {
        setResults(found);
      }
      return found;
    } catch (e) {
      if (seq === findSeq.current) {
        setError(toSearchError(e, "Search failed"));
      }
      return null;
    } finally {
      if (seq === findSeq.current) {
        setSearching(false);
      }
    }
  };

  return {
    segmentImage,
    findSimilar,
    items,
    segmentSize,
    results,
    segmenting,
    searching,
    error,
  };
}
