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

// Hosted from the repo's docs/ folder via GitHub Pages (see HANDOFF.md).
// Required by App Store guidelines 5.1.1(i) (privacy policy accessible
// in-app) and 1.5 (support contact).
export const PRIVACY_POLICY_URL =
  "https://andrewk1230.github.io/ClothingApp/privacy-policy";
export const TERMS_URL = "https://andrewk1230.github.io/ClothingApp/terms";
export const SUPPORT_URL = "https://andrewk1230.github.io/ClothingApp/support";
