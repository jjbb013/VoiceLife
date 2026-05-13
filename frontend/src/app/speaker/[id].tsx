import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
} from 'react-native';
import {
  Appbar,
  Card,
  Chip,
  Text,
  Avatar,
  Divider,
  ActivityIndicator,
  Snackbar,
  useTheme,
  Button,
  IconButton,
  Surface,
  ProgressBar,
} from 'react-native-paper';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';

import { SpeakerDetail, SpeakerEvent, Utterance } from '../../types';
import { useApi } from '../../hooks/useApi';
import { API } from '../../constants';

// Mock data
const MOCK_SPEAKER: SpeakerDetail = {
  id: '1',
  name: '张三',
  relationship: '同事',
  bio: '项目组资深后端工程师，10年工作经验',
  voiceprint_count: 12,
  total_duration: 3600,
  utterance_count: 45,
  last_met: new Date(Date.now() - 86400000).toISOString(),
  created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
  updated_at: new Date(Date.now() - 86400000).toISOString(),
  ai_summary: '张三是一位资深后端工程师，技术能力扎实，擅长系统架构设计。在最近的对话中经常讨论微服务拆分、数据库优化等技术话题。他对新技术保持好奇心，善于提出建设性的技术方案。',
  events: [
    {
      id: 'e1',
      type: 'meeting',
      title: '项目周会',
      description: '讨论Q4技术规划',
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      recording_id: 'r1',
    },
    {
      id: 'e2',
      type: 'conversation',
      title: '技术讨论',
      description: '讨论微服务拆分方案',
      timestamp: new Date(Date.now() - 3 * 86400000).toISOString(),
      recording_id: 'r2',
    },
    {
      id: 'e3',
      type: 'milestone',
      title: '首次识别',
      description: '系统首次识别到该说话人',
      timestamp: new Date(Date.now() - 30 * 86400000).toISOString(),
    },
  ],
  voiceprints: [
    { id: 'v1', created_at: new Date(Date.now() - 30 * 86400000).toISOString(), sample_duration: 30, is_active: true },
    { id: 'v2', created_at: new Date(Date.now() - 20 * 86400000).toISOString(), sample_duration: 45, is_active: true },
    { id: 'v3', created_at: new Date(Date.now() - 10 * 86400000).toISOString(), sample_duration: 60, is_active: true },
  ],
};

const MOCK_UTTERANCES: Utterance[] = [
  {
    id: 'u1',
    recording_id: 'r1',
    speaker_id: '1',
    text: '我先说一下微服务这块的进展，目前我们已经完成了服务拆分的初步设计。',
    start_time: 0,
    end_time: 8,
    confidence: 0.95,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'u2',
    recording_id: 'r2',
    speaker_id: '1',
    text: '数据库索引优化这块，我建议先用 EXPLAIN 分析一下慢查询。',
    start_time: 120,
    end_time: 135,
    confidence: 0.91,
    emotion: 'happy',
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
  {
    id: 'u3',
    recording_id: 'r2',
    speaker_id: '1',
    text: 'Redis 缓存方案我觉得可以，但要注意缓存穿透的问题。',
    start_time: 200,
    end_time: 210,
    confidence: 0.88,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
];

const EVENT_ICONS: Record<string, string> = {
  meeting: 'office-building',
  conversation: 'message-text',
  note: 'note-text',
  milestone: 'flag',
};

const EVENT_COLORS: Record<string, string> = {
  meeting: '#6200ee',
  conversation: '#03dac6',
  note: '#FF9800',
  milestone: '#4CAF50',
};

export default function SpeakerDetailScreen() {
  const theme = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const api = useApi();

  const [speaker, setSpeaker] = useState<SpeakerDetail>(MOCK_SPEAKER);
  const [utterances, setUtterances] = useState<Utterance[]>(MOCK_UTTERANCES);
  const [loading, setLoading] = useState(true);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setSpeaker({ ...MOCK_SPEAKER, id });
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [id]);

  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    const remainingMins = mins % 60;
    if (hrs > 0) return `${hrs}小时${remainingMins}分钟`;
    return `${mins}分钟`;
  };

  const formatDate = (dateStr: string): string => {
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

  const handleEdit = useCallback(() => {
    showSnackbar('编辑功能即将上线');
  }, [showSnackbar]);

  const handleEventPress = useCallback((recordingId?: string) => {
    if (recordingId) {
      router.push(`/recording/${recordingId}`);
    }
  }, [router]);

  if (loading) {
    return (
      <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <StatusBar style={theme.dark ? 'light' : 'dark'} />
        <Appbar.Header elevated>
          <Appbar.BackAction onPress={() => router.back()} />
          <Appbar.Content title="加载中..." />
        </Appbar.Header>
        <View style={styles.loadingContainer}>
          <ActivityIndicator animating size="large" color={theme.colors.primary} />
        </View>
      </View>
    );
  }

  const initials = speaker.name ? speaker.name.charAt(0).toUpperCase() : '?';

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      <Appbar.Header elevated>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content
          title={speaker.name || `未知-${speaker.id.slice(-4)}`}
          titleStyle={styles.headerTitle}
        />
        <Appbar.Action icon="pencil" onPress={handleEdit} />
      </Appbar.Header>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Header */}
        <Surface style={styles.profileHeader} elevation={1}>
          <Avatar.Text
            size={80}
            label={initials}
            style={{ backgroundColor: theme.colors.primaryContainer }}
            color={theme.colors.onPrimaryContainer}
          />
          <Text variant="headlineSmall" style={[styles.name, { color: theme.colors.onSurface }]}>
            {speaker.name || `未知-${speaker.id.slice(-4)}`}
          </Text>
          {speaker.relationship && (
            <Chip
              style={[styles.relationshipChip, { backgroundColor: theme.colors.primary + '18' }]}
              textStyle={{ color: theme.colors.primary }}
            >
              {speaker.relationship}
            </Chip>
          )}
          {speaker.bio && (
            <Text
              variant="bodyMedium"
              style={[styles.bio, { color: theme.colors.onSurfaceVariant }]}
            >
              {speaker.bio}
            </Text>
          )}
        </Surface>

        {/* Stats Row */}
        <View style={styles.statsRow}>
          <Surface style={styles.statCard} elevation={1}>
            <MaterialCommunityIcons
              name="clock-outline"
              size={24}
              color={theme.colors.primary}
            />
            <Text variant="titleMedium" style={styles.statValue}>
              {formatDuration(speaker.total_duration)}
            </Text>
            <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
              累计对话
            </Text>
          </Surface>
          <Surface style={styles.statCard} elevation={1}>
            <MaterialCommunityIcons
              name="message-text"
              size={24}
              color={theme.colors.primary}
            />
            <Text variant="titleMedium" style={styles.statValue}>
              {speaker.utterance_count}
            </Text>
            <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
              对话条数
            </Text>
          </Surface>
          <Surface style={styles.statCard} elevation={1}>
            <MaterialCommunityIcons
              name="account-voice"
              size={24}
              color={theme.colors.primary}
            />
            <Text variant="titleMedium" style={styles.statValue}>
              {speaker.voiceprint_count}
            </Text>
            <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
              声纹样本
            </Text>
          </Surface>
        </View>

        {/* AI Summary Card */}
        {speaker.ai_summary && (
          <Card style={styles.summaryCard} mode="elevated">
            <Card.Content>
              <View style={styles.cardHeader}>
                <MaterialCommunityIcons name="brain" size={20} color={theme.colors.primary} />
                <Text variant="titleSmall" style={styles.cardTitle}>
                  AI 人物画像
                </Text>
              </View>
              <Text
                variant="bodyMedium"
                style={{ lineHeight: 22, color: theme.colors.onSurfaceVariant }}
              >
                {speaker.ai_summary}
              </Text>
            </Card.Content>
          </Card>
        )}

        {/* Voiceprints Section */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            声纹管理
          </Text>
          <Card mode="outlined" style={styles.voiceprintCard}>
            {speaker.voiceprints.map((vp, index) => (
              <View key={vp.id}>
                <View style={styles.voiceprintItem}>
                  <View style={styles.voiceprintInfo}>
                    <MaterialCommunityIcons
                      name="waveform"
                      size={20}
                      color={vp.is_active ? theme.colors.primary : theme.colors.outline}
                    />
                    <View style={styles.voiceprintMeta}>
                      <Text variant="bodyMedium">声纹样本 #{index + 1}</Text>
                      <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
                        {formatDate(vp.created_at)} · {vp.sample_duration}秒
                      </Text>
                    </View>
                  </View>
                  <IconButton
                    icon={vp.is_active ? 'check-circle' : 'circle-outline'}
                    size={20}
                    iconColor={vp.is_active ? theme.colors.primary : theme.colors.outline}
                  />
                </View>
                {index < speaker.voiceprints.length - 1 && <Divider />}
              </View>
            ))}
          </Card>
        </View>

        {/* Timeline Section */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            事件时间线
          </Text>
          <Card mode="outlined" style={styles.timelineCard}>
            {speaker.events.map((event, index) => (
              <View key={event.id} style={styles.timelineItem}>
                <View style={styles.timelineLeft}>
                  <View
                    style={[
                      styles.timelineDot,
                      { backgroundColor: EVENT_COLORS[event.type] || theme.colors.primary },
                    ]}
                  >
                    <MaterialCommunityIcons
                      name={EVENT_ICONS[event.type] as any}
                      size={12}
                      color="#fff"
                    />
                  </View>
                  {index < speaker.events.length - 1 && (
                    <View style={[styles.timelineLine, { backgroundColor: theme.colors.outlineVariant }]} />
                  )}
                </View>
                <View style={styles.timelineContent}>
                  <Text variant="bodyMedium" style={{ fontWeight: '600' }}>
                    {event.title}
                  </Text>
                  {event.description && (
                    <Text
                      variant="bodySmall"
                      style={{ color: theme.colors.onSurfaceVariant, marginTop: 2 }}
                    >
                      {event.description}
                    </Text>
                  )}
                  <Text variant="labelSmall" style={{ color: theme.colors.outline, marginTop: 2 }}>
                    {formatDate(event.timestamp)}
                  </Text>
                  {event.recording_id && (
                    <Button
                      mode="text"
                      compact
                      onPress={() => handleEventPress(event.recording_id)}
                      style={{ alignSelf: 'flex-start', marginTop: 4 }}
                    >
                      查看录音
                    </Button>
                  )}
                </View>
              </View>
            ))}
          </Card>
        </View>

        {/* Recent Utterances */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            最近对话
          </Text>
          {utterances.length === 0 ? (
            <View style={styles.emptyContainer}>
              <MaterialCommunityIcons
                name="message-off"
                size={48}
                color={theme.colors.outline}
              />
              <Text
                variant="bodyMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginTop: 8 }}
              >
                暂无对话记录
              </Text>
            </View>
          ) : (
            utterances.map((utterance) => (
              <Card
                key={utterance.id}
                style={styles.utteranceCard}
                mode="elevated"
                onPress={() => router.push(`/recording/${utterance.recording_id}`)}
              >
                <Card.Content style={styles.utteranceContent}>
                  <View style={styles.utteranceHeader}>
                    <View style={styles.confidenceRow}>
                      <MaterialCommunityIcons
                        name="waveform"
                        size={14}
                        color={theme.colors.primary}
                      />
                      <Text variant="labelSmall" style={{ color: theme.colors.outline, marginLeft: 4 }}>
                        置信度 {Math.round(utterance.confidence * 100)}%
                      </Text>
                    </View>
                    <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
                      {formatDate(utterance.created_at)}
                    </Text>
                  </View>
                  <Text
                    variant="bodyMedium"
                    numberOfLines={2}
                    style={{ marginTop: 4, lineHeight: 20 }}
                  >
                    {utterance.text}
                  </Text>
                </Card.Content>
              </Card>
            ))
          )}
        </View>
      </ScrollView>

      {/* Snackbar */}
      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
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
  headerTitle: {
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  profileHeader: {
    alignItems: 'center',
    paddingVertical: 24,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 16,
  },
  name: {
    fontWeight: '700',
    marginTop: 12,
  },
  relationshipChip: {
    marginTop: 8,
    height: 28,
  },
  bio: {
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  statsRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 12,
    gap: 8,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
  },
  statValue: {
    fontWeight: '700',
    marginTop: 4,
  },
  summaryCard: {
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardTitle: {
    fontWeight: '600',
    marginLeft: 8,
  },
  section: {
    marginTop: 16,
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontWeight: '600',
    marginBottom: 8,
  },
  voiceprintCard: {
    borderRadius: 12,
  },
  voiceprintItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  voiceprintInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  voiceprintMeta: {
    marginLeft: 12,
  },
  timelineCard: {
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  timelineItem: {
    flexDirection: 'row',
    paddingVertical: 10,
  },
  timelineLeft: {
    alignItems: 'center',
    width: 28,
  },
  timelineDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  timelineLine: {
    width: 2,
    flex: 1,
    marginVertical: 2,
  },
  timelineContent: {
    flex: 1,
    marginLeft: 12,
    paddingBottom: 8,
  },
  utteranceCard: {
    marginBottom: 8,
    borderRadius: 12,
  },
  utteranceContent: {
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  utteranceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  confidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
});
