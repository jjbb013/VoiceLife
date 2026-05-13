import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, Dimensions } from 'react-native';
import { useTheme } from 'react-native-paper';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const BAR_COUNT = 28;
const BAR_WIDTH = 4;
const BAR_GAP = 3;

interface RecordingWaveProps {
  isActive: boolean;
  metering?: number; // -160 ~ 0
}

export default function RecordingWave({ isActive, metering = -160 }: RecordingWaveProps) {
  const theme = useTheme();
  const animatedValues = useRef<Animated.Value[]>(
    Array.from({ length: BAR_COUNT }, () => new Animated.Value(2))
  ).current;
  const animationRefs = useRef<Animated.CompositeAnimation[]>([]);

  // Normalize metering (-160 ~ 0) to height (2 ~ 80)
  const normalizeHeight = (value: number): number => {
    const normalized = Math.max(0, Math.min(1, (value + 160) / 160));
    return 2 + normalized * 78;
  };

  useEffect(() => {
    if (isActive) {
      // Start continuous wave animation
      animatedValues.forEach((anim, index) => {
        const animation = Animated.loop(
          Animated.sequence([
            Animated.timing(anim, {
              toValue: normalizeHeight(metering) + Math.random() * 20,
              duration: 200 + index * 15,
              useNativeDriver: false,
            }),
            Animated.timing(anim, {
              toValue: 2 + Math.random() * 30,
              duration: 200 + index * 15,
              useNativeDriver: false,
            }),
          ])
        );
        animation.start();
        animationRefs.current[index] = animation;
      });
    } else {
      // Stop all animations and reset
      animationRefs.current.forEach((anim) => anim?.stop());
      animatedValues.forEach((anim) => {
        Animated.timing(anim, {
          toValue: 2,
          duration: 300,
          useNativeDriver: false,
        }).start();
      });
    }

    return () => {
      animationRefs.current.forEach((anim) => anim?.stop());
    };
  }, [isActive]);

  // Update animation when metering changes
  useEffect(() => {
    if (!isActive) return;
    const targetHeight = normalizeHeight(metering);
    animatedValues.forEach((anim, index) => {
      Animated.timing(anim, {
        toValue: Math.max(2, targetHeight * (0.5 + Math.random() * 0.5)),
        duration: 100,
        useNativeDriver: false,
      }).start();
    });
  }, [metering]);

  return (
    <View style={styles.container}>
      <View style={styles.waveContainer}>
        {animatedValues.map((anim, index) => (
          <Animated.View
            key={index}
            style={[
              styles.bar,
              {
                backgroundColor: theme.colors.primary,
                width: BAR_WIDTH,
                marginHorizontal: BAR_GAP / 2,
                height: anim,
                opacity: isActive ? 1 : 0.3,
              },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    height: 100,
    justifyContent: 'center',
    alignItems: 'center',
  },
  waveContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    width: BAR_COUNT * (BAR_WIDTH + BAR_GAP),
    height: 100,
  },
  bar: {
    borderRadius: BAR_WIDTH / 2,
  },
});
