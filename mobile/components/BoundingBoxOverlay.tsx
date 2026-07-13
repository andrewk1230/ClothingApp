import { G, Rect, Text as SvgText } from "react-native-svg";

import { DetectedItem } from "../hooks/useSearch";

interface BoundingBoxOverlayProps {
  item: DetectedItem;
  /** Multiplier from backend pixel coordinates to on-screen display coordinates. */
  scale: number;
  /** Width of the displayed image in screen points, for clamping the label chip. */
  displayWidth: number;
  strokeColor: string;
  chipColor: string;
  chipTextColor: string;
  onPress: () => void;
}

const CHIP_HEIGHT = 22;
const CHIP_FONT_SIZE = 12;

export default function BoundingBoxOverlay({
  item,
  scale,
  displayWidth,
  strokeColor,
  chipColor,
  chipTextColor,
  onPress,
}: BoundingBoxOverlayProps) {
  const x = item.bbox.x * scale;
  const y = item.bbox.y * scale;
  const w = item.bbox.w * scale;
  const h = item.bbox.h * scale;

  const label = item.category;
  const chipWidth = Math.min(label.length * 7.5 + 16, displayWidth);
  const chipX = Math.min(Math.max(x, 0), displayWidth - chipWidth);
  // Place the chip above the box; tuck it inside when the box touches the top edge.
  const chipY = y >= CHIP_HEIGHT + 4 ? y - CHIP_HEIGHT - 4 : y + 4;

  return (
    <G onPress={onPress}>
      <Rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={8}
        stroke={strokeColor}
        strokeWidth={2}
        fill="rgba(255, 255, 255, 0.08)"
      />
      <Rect
        x={chipX}
        y={chipY}
        width={chipWidth}
        height={CHIP_HEIGHT}
        rx={CHIP_HEIGHT / 2}
        fill={chipColor}
      />
      <SvgText
        x={chipX + chipWidth / 2}
        y={chipY + CHIP_HEIGHT / 2 + CHIP_FONT_SIZE / 2 - 1.5}
        fontSize={CHIP_FONT_SIZE}
        fontWeight="600"
        fill={chipTextColor}
        textAnchor="middle"
      >
        {label}
      </SvgText>
    </G>
  );
}
