import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  Animated,
  GestureResponderEvent,
} from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface FlashMemoButtonProps {
  onRecordingStart: () => void;
  onRecordingStop: (audioUri: string) => void;
  disabled?: boolean;
}

export default function FlashMemoButton({
  onRecordingStart,
  onRecordingStop,
  disabled = false,
}: FlashMemoButtonProps) {
  const theme = useTheme();
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Pulse animation when recording
  useEffect(() => {
    if (isRecording) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.3,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  // Duration counter
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setDuration(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording]);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePressIn = useCallback(
    (event: GestureResponderEvent) => {
      if (disabled) return;
      event.preventDefault?.();
      setIsRecording(true);

      Animated.timing(scaleAnim, {
        toValue: 0.92,
        duration: 100,
        useNativeDriver: true,
      }).start();

      onRecordingStart();
    },
    [disabled, onRecordingStart, scaleAnim]
  );

  const handlePressOut = useCallback(() => {
    if (!isRecording) return;
    setIsRecording(false);

    Animated.timing(scaleAnim, {
      toValue: 1,
      duration: 150,
      useNativeDriver: true,
    }).start();

    const audioUri = `file://flash_memo_${Date.now()}.m4a`;
    onRecordingStop(audioUri);
  }, [isRecording, onRecordingStop, scaleAnim]);

  return (
    <View style={styles.container}>
      {isRecording && (
        <Animated.View
          style={[
            styles.pulseRing,
            {
              backgroundColor: theme.colors.error,
              transform: [{ scale: pulseAnim }],
              opacity: pulseAnim.interpolate({
                inputRange: [1, 1.3],
                outputRange: [0.3, 0],
              }),
            },
          ]}
        />
      )}

      <Pressable
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={disabled}
        style={({ pressed }) => [styles.pressable, pressed && styles.pressed]}
      >
        <Animated.View
          style={[
            styles.button,
            {
              backgroundColor: isRecording ? theme.colors.error : theme.colors.primary,
              transform: [{ scale: scaleAnim }],
              opacity: disabled ? 0.5 : 1,
            },
          ]}
        >
          <MaterialCommunityIcons
            name={isRecording ? 'stop' : 'microphone'}
            size={36}
            color="#ffffff"
          />
        </Animated.View>
      </Pressable>

      <Text variant="labelMedium" style={[styles.label, { color: theme.colors.onSurfaceVariant }]}>
        {isRecording ? formatDuration(duration) : '闪念胶囊'}
      </Text>

      {isRecording && (
        <Text variant="labelSmall" style={[styles.hint, { color: theme.colors.error }]}>
          松手保存
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseRing: {
    position: 'absolute',
    width: 90,
    height: 90,
    borderRadius: 45,
  },
  pressable: {
    zIndex: 1,
  },
  pressed: {
    opacity: 0.9,
  },
  button: {
    width: 72,
    height: 72,
    borderRadius: 36,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 6,
  },
  label: {
    marginTop: 8,
    fontWeight: '500',
  },
  hint: {
    marginTop: 2,
    fontWeight: '600',
  },
});
