import { forwardRef, useImperativeHandle } from "react";
import { StyleSheet, View } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, { useAnimatedStyle, useSharedValue } from "react-native-reanimated";

export interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface ManualCropToolHandle {
  /** Current crop rectangle in display points, relative to the displayed image's top-left. */
  getRect: () => CropRect;
}

interface ManualCropToolProps {
  /** Width of the displayed (letterboxed) image in screen points. */
  displayWidth: number;
  /** Height of the displayed (letterboxed) image in screen points. */
  displayHeight: number;
  strokeColor: string;
}

const MIN_SIZE = 40;
const HANDLE_TOUCH_SIZE = 36;
const HANDLE_HALF = HANDLE_TOUCH_SIZE / 2;
const HANDLE_DOT_SIZE = 18;

function clamp(value: number, min: number, max: number): number {
  "worklet";
  return Math.min(Math.max(value, min), max);
}

const ManualCropTool = forwardRef<ManualCropToolHandle, ManualCropToolProps>(
  function ManualCropTool({ displayWidth, displayHeight, strokeColor }, ref) {
    // Guard against images displayed smaller than the minimum crop size.
    const minW = Math.min(MIN_SIZE, displayWidth);
    const minH = Math.min(MIN_SIZE, displayHeight);

    // Crop rect in display coordinates (points, relative to the image's display rect).
    const x = useSharedValue(displayWidth * 0.2);
    const y = useSharedValue(displayHeight * 0.2);
    const w = useSharedValue(Math.max(displayWidth * 0.6, minW));
    const h = useSharedValue(Math.max(displayHeight * 0.6, minH));

    // Rect captured at gesture start, so each pan works from a stable anchor.
    const startX = useSharedValue(0);
    const startY = useSharedValue(0);
    const startW = useSharedValue(0);
    const startH = useSharedValue(0);

    useImperativeHandle(ref, () => ({
      getRect: () => ({ x: x.value, y: y.value, w: w.value, h: h.value }),
    }));

    const captureStart = () => {
      "worklet";
      startX.value = x.value;
      startY.value = y.value;
      startW.value = w.value;
      startH.value = h.value;
    };

    const bodyPan = Gesture.Pan()
      .onStart(captureStart)
      .onUpdate((event) => {
        x.value = clamp(startX.value + event.translationX, 0, displayWidth - w.value);
        y.value = clamp(startY.value + event.translationY, 0, displayHeight - h.value);
      });

    const makeCornerPan = (isLeft: boolean, isTop: boolean) =>
      Gesture.Pan()
        .onStart(captureStart)
        .onUpdate((event) => {
          if (isLeft) {
            const newX = clamp(
              startX.value + event.translationX,
              0,
              startX.value + startW.value - minW
            );
            x.value = newX;
            w.value = startX.value + startW.value - newX;
          } else {
            w.value = clamp(
              startW.value + event.translationX,
              minW,
              displayWidth - startX.value
            );
          }
          if (isTop) {
            const newY = clamp(
              startY.value + event.translationY,
              0,
              startY.value + startH.value - minH
            );
            y.value = newY;
            h.value = startY.value + startH.value - newY;
          } else {
            h.value = clamp(
              startH.value + event.translationY,
              minH,
              displayHeight - startY.value
            );
          }
        });

    const tlPan = makeCornerPan(true, true);
    const trPan = makeCornerPan(false, true);
    const blPan = makeCornerPan(true, false);
    const brPan = makeCornerPan(false, false);

    const rectStyle = useAnimatedStyle(() => ({
      transform: [{ translateX: x.value }, { translateY: y.value }],
      width: w.value,
      height: h.value,
    }));

    const tlStyle = useAnimatedStyle(() => ({
      transform: [
        { translateX: x.value - HANDLE_HALF },
        { translateY: y.value - HANDLE_HALF },
      ],
    }));
    const trStyle = useAnimatedStyle(() => ({
      transform: [
        { translateX: x.value + w.value - HANDLE_HALF },
        { translateY: y.value - HANDLE_HALF },
      ],
    }));
    const blStyle = useAnimatedStyle(() => ({
      transform: [
        { translateX: x.value - HANDLE_HALF },
        { translateY: y.value + h.value - HANDLE_HALF },
      ],
    }));
    const brStyle = useAnimatedStyle(() => ({
      transform: [
        { translateX: x.value + w.value - HANDLE_HALF },
        { translateY: y.value + h.value - HANDLE_HALF },
      ],
    }));

    return (
      <View style={styles.container} pointerEvents="box-none">
        <GestureDetector gesture={bodyPan}>
          <Animated.View style={[styles.rect, { borderColor: strokeColor }, rectStyle]} />
        </GestureDetector>
        <GestureDetector gesture={tlPan}>
          <Animated.View style={[styles.handle, tlStyle]}>
            <View style={styles.handleDot} />
          </Animated.View>
        </GestureDetector>
        <GestureDetector gesture={trPan}>
          <Animated.View style={[styles.handle, trStyle]}>
            <View style={styles.handleDot} />
          </Animated.View>
        </GestureDetector>
        <GestureDetector gesture={blPan}>
          <Animated.View style={[styles.handle, blStyle]}>
            <View style={styles.handleDot} />
          </Animated.View>
        </GestureDetector>
        <GestureDetector gesture={brPan}>
          <Animated.View style={[styles.handle, brStyle]}>
            <View style={styles.handleDot} />
          </Animated.View>
        </GestureDetector>
      </View>
    );
  }
);

export default ManualCropTool;

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    overflow: "visible",
  },
  rect: {
    position: "absolute",
    left: 0,
    top: 0,
    borderWidth: 2,
    borderRadius: 8,
    backgroundColor: "rgba(255, 255, 255, 0.12)",
  },
  handle: {
    position: "absolute",
    left: 0,
    top: 0,
    width: HANDLE_TOUCH_SIZE,
    height: HANDLE_TOUCH_SIZE,
    alignItems: "center",
    justifyContent: "center",
  },
  handleDot: {
    width: HANDLE_DOT_SIZE,
    height: HANDLE_DOT_SIZE,
    borderRadius: HANDLE_DOT_SIZE / 2,
    backgroundColor: "#FFFFFF",
    borderWidth: 2,
    borderColor: "rgba(0, 0, 0, 0.35)",
  },
});
