import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Card, Avatar, Text, useTheme } from 'react-native-paper';
import { Utterance, EmotionEmoji } from '../types';

interface UtteranceBubbleProps {
  utterance: Utterance;
  speakerName: string;
  isMaster?: boolean;
}

export default function UtteranceBubble({
  utterance,
  speakerName,
  isMaster = false,
}: UtteranceBubbleProps) {
  const theme = useTheme();

  const emotion = utterance.emotion || 'neutral';
  const emoji = EmotionEmoji[emotion] || EmotionEmoji.neutral;
  const initials = speakerName.charAt(0).toUpperCase();

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const confidenceColor =
    utterance.confidence > 0.8
      ? theme.colors.primary
      : utterance.confidence > 0.5
      ? theme.colors.secondary
      : theme.colors.error;

  return (
    <View
      style={[
        styles.container,
        isMaster ? styles.masterContainer : styles.otherContainer,
      ]}
    >
      {!isMaster && (
        <Avatar.Text
          size={32}
          label={initials}
          style={[styles.avatar, { backgroundColor: theme.colors.secondaryContainer }]}
          color={theme.colors.onSecondaryContainer}
        />
      )}

      <View style={[styles.bubbleColumn, isMaster ? styles.masterColumn : styles.otherColumn]}>
        {!isMaster && (
          <View style={styles.speakerRow}>
            <Text variant="labelSmall" style={[styles.speakerName, { color: theme.colors.primary }]}>
              {speakerName}
            </Text>
            <Text style={styles.emoji}>{emoji}</Text>
          </View>
        )}

        {isMaster && (
          <View style={[styles.speakerRow, styles.masterSpeakerRow]}>
            <Text style={styles.emoji}>{emoji}</Text>
            <Text variant="labelSmall" style={[styles.speakerName, { color: theme.colors.primary }]}>
              我
            </Text>
          </View>
        )}

        <Card
          style={[
            styles.bubble,
            isMaster
              ? { backgroundColor: theme.colors.primaryContainer }
              : { backgroundColor: theme.colors.surfaceVariant },
          ]}
          mode="outlined"
          outlineColor="transparent"
        >
          <Card.Content style={styles.bubbleContent}>
            <Text
              variant="bodyMedium"
              style={[
                styles.utteranceText,
                { color: isMaster ? theme.colors.onPrimaryContainer : theme.colors.onSurfaceVariant },
              ]}
            >
              {utterance.text}
            </Text>
          </Card.Content>
        </Card>

        <View style={[styles.footerRow, isMaster ? styles.masterFooter : styles.otherFooter]}>
          <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
            {formatTime(utterance.start_time)}
          </Text>
          <View
            style={[
              styles.confidenceDot,
              { backgroundColor: confidenceColor },
            ]}
          />
          <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
            {Math.round(utterance.confidence * 100)}%
          </Text>
        </View>
      </View>

      {isMaster && (
        <Avatar.Text
          size={32}
          label="我"
          style={[styles.avatar, { backgroundColor: theme.colors.primaryContainer }]}
          color={theme.colors.onPrimaryContainer}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    marginVertical: 6,
    paddingHorizontal: 12,
    maxWidth: '85%',
  },
  masterContainer: {
    alignSelf: 'flex-end',
    flexDirection: 'row',
  },
  otherContainer: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
  },
  avatar: {
    marginTop: 4,
  },
  bubbleColumn: {
    marginHorizontal: 8,
    flex: 1,
  },
  masterColumn: {
    alignItems: 'flex-end',
  },
  otherColumn: {
    alignItems: 'flex-start',
  },
  speakerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  masterSpeakerRow: {
    justifyContent: 'flex-end',
  },
  speakerName: {
    fontWeight: '600',
  },
  emoji: {
    fontSize: 12,
    marginLeft: 4,
  },
  bubble: {
    borderRadius: 16,
    minWidth: 60,
  },
  bubbleContent: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  utteranceText: {
    lineHeight: 20,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  masterFooter: {
    justifyContent: 'flex-end',
  },
  otherFooter: {
    justifyContent: 'flex-start',
  },
  confidenceDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginHorizontal: 4,
  },
});
