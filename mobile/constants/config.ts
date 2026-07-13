export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const CONFIDENCE_THRESHOLDS = {
  SEGMENTATION_MIN: 0.3,
  SEARCH_CONFIDENT: 0.7,
  SEARCH_SIMILAR: 0.4,
};

export const IMAGE_MAX_DIMENSION = 1024;
export const IMAGE_COMPRESSION_QUALITY = 0.8;

export const SEARCH_RESULTS_LIMIT = 20;
export const GUEST_DAILY_LIMIT = 5;
export const USER_DAILY_LIMIT = 50;

export const THEME_PREFERENCE_KEY = "theme_preference";
export const ONBOARDING_COMPLETE_KEY = "onboarding_complete";
