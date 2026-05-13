import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Card, Avatar, Chip, Text, useTheme } from 'react-native-paper';
import { Speaker } from '../types';

interface SpeakerCardProps {
  speaker: Speaker;
  onPress?: () => void;
  onLongPress?: () => void;
}

export default function SpeakerCard({ speaker, onPress, onLongPress }: SpeakerCardProps) {
  const theme = useTheme();

  const displayName = speaker.name || `未知-${speaker.id.slice(-4)}`;
  const initials = displayName.charAt(0).toUpperCase();
  const relationshipColor = speaker.relationship ? theme.colors.primary : theme.colors.outline;

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`;
    return `${(seconds / 3600).toFixed(1)}小时`;
  };

  const formatTime = (dateStr?: string): string => {
    if (!dateStr) return '从未';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (days < 30) return `${Math.floor(days / 7)}周前`;
    return `${Math.floor(days / 30)}个月前`;
  };

  return (
    <Pressable onPress={onPress} onLongPress={onLongPress}>
      <Card style={styles.card} mode="elevated">
        <Card.Content style={styles.content}>
          <View style={styles.header}>
            <Avatar.Text
              size={56}
              label={initials}
              style={{ backgroundColor: theme.colors.primaryContainer }}
              color={theme.colors.onPrimaryContainer}
            />
            <View style={styles.headerInfo}>
              <Text variant="titleMedium" numberOfLines={1} style={styles.name}>
                {displayName}
              </Text>
              {speaker.relationship && (
                <Chip
                  compact
                  style={[styles.relationshipChip, { backgroundColor: relationshipColor + '18' }]}
                  textStyle={{ color: relationshipColor, fontSize: 11 }}
                >
                  {speaker.relationship}
                </Chip>
              )}
            </View>
          </View>

          {speaker.ai_summary && (
            <Text
              variant="bodySmall"
              numberOfLines={2}
              style={[styles.summary, { color: theme.colors.onSurfaceVariant }]}
            >
              {speaker.ai_summary}
            </Text>
          )}

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
                声纹样本
              </Text>
              <Text variant="titleSmall" style={styles.statValue}>
                {speaker.voiceprint_count}
              </Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
                累计对话
              </Text>
              <Text variant="titleSmall" style={styles.statValue}>
                {formatDuration(speaker.total_duration)}
              </Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
                最近对话
              </Text>
              <Text variant="titleSmall" style={styles.statValue}>
                {formatTime(speaker.last_met)}
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginVertical: 6,
    borderRadius: 12,
  },
  content: {
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerInfo: {
    marginLeft: 14,
    flex: 1,
  },
  name: {
    fontWeight: '600',
  },
  relationshipChip: {
    alignSelf: 'flex-start',
    marginTop: 2,
    height: 24,
  },
  summary: {
    marginTop: 8,
    lineHeight: 18,
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statDivider: {
    width: 1,
    backgroundColor: '#e0e0e0',
  },
  statValue: {
    fontWeight: '600',
    marginTop: 2,
  },
});
