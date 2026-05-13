import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Dimensions,
  Animated,
} from 'react-native';
import {
  Appbar,
  Text,
  Card,
  Avatar,
  Chip,
  IconButton,
  Snackbar,
  Surface,
  useTheme,
  Portal,
} from 'react-native-paper';
import { useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';

import RecordingWave from '../../components/RecordingWave';
import FlashMemoButton from '../../components/FlashMemoButton';
import MeetingToggle from '../../components/MeetingToggle';
import { useRecording } from '../../hooks/useRecording';
import { StatusColor } from '../../types';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Mock detected speakers data
const MOCK_SPEAKERS = [
  { id: '1', name: '张三', initials: '张', confidence: 0.95 },
  { id: '2', name: '李四', initials: '李', confidence: 0.88 },
  { id: '3', name: '王五', initials: '王', confidence: 0.72 },
];

// Mock recent utterances
const MOCK_RECENT = [
  {
    id: '1',
    text: '我觉得这个方案还不错，但是预算方面需要再考虑一下',
    speaker: '张三',
    time: '2分钟前',
  },
  {
    id: '2',
    text: '对，预算是个问题，我们可能需要分阶段实施',
    speaker: '李四',
    time: '1分钟前',
  },
  {
    id: '3',
    text: '那我们先做第一阶段吧，后续再评估效果',
    speaker: '我',
    time: '刚刚',
  },
];

export default function HomeScreen() {
  const theme = useTheme();
  const router = useRouter();
  const recording = useRecording();

  const [isOnline, setIsOnline] = useState(true);
  const [isMeetingMode, setIsMeetingMode] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [recentUtterances, setRecentUtterances] = useState(MOCK_RECENT);
  const [scaleAnim] = useState(new Animated.Value(1));

  // Show snackbar helper
  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  // Auto-start listening on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      recording.startListening();
      showSnackbar('已开始监听环境声音');
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  // Animate status indicator
  useEffect(() => {
    if (recording.isRecording || recording.isAnalyzing) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(scaleAnim, {
            toValue: 1.15,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.timing(scaleAnim, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      scaleAnim.setValue(1);
    }
  }, [recording.status]);

  // Flash memo handlers
  const handleFlashMemoStart = useCallback(() => {
    recording.startRecording();
    showSnackbar('闪念胶囊录音中...');
  }, [recording, showSnackbar]);

  const handleFlashMemoStop = useCallback(
    (audioUri: string) => {
      showSnackbar('闪念胶囊已保存');
      // Add mock utterance
      setRecentUtterances((prev) => [
        {
          id: Date.now().toString(),
          text: '[闪念胶囊] 新的语音备忘录',
          speaker: '我',
          time: '刚刚',
        },
        ...prev.slice(0, 2),
      ]);
    },
    [showSnackbar]
  );

  // Meeting mode toggle
  const handleMeetingToggle = useCallback(
    (value: boolean) => {
      setIsMeetingMode(value);
      showSnackbar(value ? '会议模式已开启' : '会议模式已关闭');
    },
    [showSnackbar]
  );

  // Pause/Resume
  const handlePauseToggle = useCallback(() => {
    recording.togglePause();
    showSnackbar(
      recording.isPaused ? '录音已恢复' : '录音已暂停'
    );
  }, [recording, showSnackbar]);

  // Get status display
  const getStatusInfo = () => {
    switch (recording.status) {
      case 'listening':
        return { label: '监听中', color: StatusColor.listening, icon: 'ear-hearing' };
      case 'recording':
        return { label: '录音中', color: StatusColor.recording, icon: 'record-circle' };
      case 'analyzing':
        return { label: '分析中', color: StatusColor.analyzing, icon: 'brain' };
      case 'paused':
        return { label: '已暂停', color: StatusColor.paused, icon: 'pause-circle' };
      default:
        return { label: '待命中', color: StatusColor.idle, icon: 'sleep' };
    }
  };

  const statusInfo = getStatusInfo();
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      {/* Top App Bar */}
      <Surface style={[styles.appBar, { backgroundColor: theme.colors.elevation.level2 }]} elevation={1}>
        <Appbar.Content
          title="AILife"
          titleStyle={[styles.appBarTitle, { color: theme.colors.primary }]}
        />
        <View style={styles.connectionStatus}>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: isOnline ? '#4CAF50' : '#F44336' },
            ]}
          />
          <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
            {isOnline ? '在线' : '离线'}
          </Text>
        </View>
      </Surface>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Status Indicator */}
        <Surface style={styles.statusCard} elevation={2}>
          <Animated.View
            style={[
              styles.statusCircle,
              {
                borderColor: statusInfo.color,
                transform: [{ scale: scaleAnim }],
              },
            ]}
          >
            <MaterialCommunityIcons
              name={statusInfo.icon as any}
              size={48}
              color={statusInfo.color}
            />
          </Animated.View>

          <Text
            variant="headlineSmall"
            style={[styles.statusLabel, { color: statusInfo.color }]}
          >
            {statusInfo.label}
          </Text>

          {(recording.isRecording || recording.isPaused) && (
            <Text variant="titleLarge" style={styles.timerText}>
              {formatDuration(recording.duration)}
            </Text>
          )}

          {recording.isAnalyzing && (
            <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant, marginTop: 4 }}>
              AI 正在分析语音...
            </Text>
          )}
        </Surface>

        {/* Wave Animation */}
        <RecordingWave
          isActive={recording.isRecording || recording.isListening}
          metering={recording.metering}
        />

        {/* Detected Speakers */}
        <View style={styles.speakersSection}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            检测到的说话人
          </Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.speakersScroll}
          >
            {MOCK_SPEAKERS.map((speaker) => (
              <Chip
                key={speaker.id}
                avatar={
                  <Avatar.Text
                    size={24}
                    label={speaker.initials}
                    style={{ backgroundColor: theme.colors.secondaryContainer }}
                    color={theme.colors.onSecondaryContainer}
                  />
                }
                style={styles.speakerChip}
                onPress={() => router.push(`/speaker/${speaker.id}`)}
              >
                {speaker.name} ({Math.round(speaker.confidence * 100)}%)
              </Chip>
            ))}
          </ScrollView>
        </View>

        {/* Quick Actions */}
        <Surface style={styles.actionsCard} elevation={1}>
          <View style={styles.actionsRow}>
            {/* Flash Memo */}
            <FlashMemoButton
              onRecordingStart={handleFlashMemoStart}
              onRecordingStop={handleFlashMemoStop}
              disabled={recording.isAnalyzing}
            />

            {/* Meeting Mode */}
            <View style={styles.meetingAction}>
              <MeetingToggle
                isMeetingMode={isMeetingMode}
                onToggle={handleMeetingToggle}
              />
            </View>

            {/* Pause/Resume */}
            <View style={styles.pauseAction}>
              <IconButton
                icon={recording.isPaused ? 'play' : 'pause'}
                size={32}
                iconColor={theme.colors.primary}
                containerColor={
                  recording.isPaused
                    ? theme.colors.primaryContainer
                    : theme.colors.surfaceVariant
                }
                onPress={handlePauseToggle}
                style={styles.pauseButton}
              />
              <Text
                variant="labelMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginTop: 4 }}
              >
                {recording.isPaused ? '继续' : '暂停'}
              </Text>
            </View>
          </View>
        </Surface>

        {/* Recent Utterances */}
        <View style={styles.recentSection}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            最近动态
          </Text>
          {recentUtterances.map((utterance) => (
            <Card
              key={utterance.id}
              style={styles.recentCard}
              mode="elevated"
              onPress={() => router.push('/(tabs)/search')}
            >
              <Card.Content style={styles.recentCardContent}>
                <View style={styles.recentHeader}>
                  <View style={styles.recentSpeaker}>
                    <Avatar.Text
                      size={28}
                      label={utterance.speaker.charAt(0)}
                      style={{ backgroundColor: theme.colors.secondaryContainer }}
                      color={theme.colors.onSecondaryContainer}
                    />
                    <Text
                      variant="labelMedium"
                      style={{ marginLeft: 8, fontWeight: '600' }}
                    >
                      {utterance.speaker}
                    </Text>
                  </View>
                  <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
                    {utterance.time}
                  </Text>
                </View>
                <Text
                  variant="bodyMedium"
                  numberOfLines={2}
                  style={{ marginTop: 8, lineHeight: 20 }}
                >
                  {utterance.text}
                </Text>
              </Card.Content>
            </Card>
          ))}
        </View>
      </ScrollView>

      {/* Snackbar */}
      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
        action={{ label: '关闭', onPress: () => setSnackbarVisible(false) }}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  appBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 48,
    paddingBottom: 12,
  },
  appBarTitle: {
    fontSize: 24,
    fontWeight: '700',
    letterSpacing: 1,
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    position: 'absolute',
    right: 16,
    top: 52,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  statusCard: {
    marginHorizontal: 20,
    marginTop: 16,
    paddingVertical: 24,
    borderRadius: 20,
    alignItems: 'center',
  },
  statusCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'transparent',
  },
  statusLabel: {
    marginTop: 12,
    fontWeight: '700',
  },
  timerText: {
    marginTop: 4,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  speakersSection: {
    marginTop: 16,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontWeight: '600',
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  speakersScroll: {
    paddingRight: 16,
  },
  speakerChip: {
    marginRight: 8,
    marginBottom: 4,
  },
  actionsCard: {
    marginHorizontal: 20,
    marginTop: 20,
    paddingVertical: 16,
    paddingHorizontal: 12,
    borderRadius: 16,
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  meetingAction: {
    flex: 1,
    alignItems: 'center',
  },
  pauseAction: {
    alignItems: 'center',
  },
  pauseButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
  },
  recentSection: {
    marginTop: 20,
    paddingHorizontal: 16,
  },
  recentCard: {
    marginBottom: 8,
    borderRadius: 12,
  },
  recentCardContent: {
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  recentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  recentSpeaker: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
