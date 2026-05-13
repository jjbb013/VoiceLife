import React, { useState, useCallback, useEffect } from 'react';
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
  Divider,
  ActivityIndicator,
  Snackbar,
  useTheme,
  Avatar,
  IconButton,
  Surface,
} from 'react-native-paper';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';

import UtteranceBubble from '../../components/UtteranceBubble';
import { RecordingDetail, Utterance, Speaker } from '../../types';
import { useApi } from '../../hooks/useApi';
import { API } from '../../constants';

// Mock data
const MOCK_RECORDING: RecordingDetail = {
  id: 'r1',
  title: '项目周会',
  duration: 1800,
  location: '会议室A',
  latitude: 39.9,
  longitude: 116.4,
  is_meeting: true,
  is_flash_memo: false,
  is_processing: false,
  is_paused: false,
  utterance_count: 45,
  speaker_count: 4,
  ai_summary: '本次会议讨论了Q4季度技术规划，确定了三个重点方向：微服务架构升级、数据库迁移、以及前端性能优化。张三负责微服务方案设计，李四主导数据库迁移。',
  topics: ['技术规划', '微服务', '数据库迁移', '性能优化'],
  meeting_minutes: '# 会议纪要\n\n## 参会人员\n- 张三（后端负责人）\n- 李四（DBA）\n- 王五（前端负责人）\n- 赵六（项目经理）\n\n## 决议事项\n1. Q4 优先完成微服务架构设计\n2. 数据库迁移计划在11月启动\n3. 前端性能目标：首屏加载 < 2s',
  created_at: new Date(Date.now() - 86400000).toISOString(),
  updated_at: new Date(Date.now() - 86400000).toISOString(),
  utterances: [],
  speakers: [],
};

const MOCK_UTTERANCES: Utterance[] = [
  {
    id: 'u1',
    recording_id: 'r1',
    speaker_id: '1',
    speaker_name: '张三',
    text: '我先说一下微服务这块的进展，目前我们已经完成了服务拆分的初步设计。',
    start_time: 0,
    end_time: 8,
    confidence: 0.95,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'u2',
    recording_id: 'r1',
    speaker_id: 'me',
    speaker_name: '我',
    text: '拆分粒度是怎么确定的？我印象中上次讨论的时候还有一些争议。',
    start_time: 10,
    end_time: 18,
    confidence: 0.92,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'u3',
    recording_id: 'r1',
    speaker_id: '1',
    speaker_name: '张三',
    text: '对，上次确实有不同的意见。最终我们决定按照业务域来拆分，每个服务负责一个独立的业务能力。',
    start_time: 20,
    end_time: 30,
    confidence: 0.88,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'u4',
    recording_id: 'r1',
    speaker_id: '2',
    speaker_name: '李四',
    text: '数据库这边我补充一下，迁移方案已经写好了，主要是分阶段进行，先迁移非核心业务。',
    start_time: 32,
    end_time: 42,
    confidence: 0.91,
    emotion: 'neutral',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'u5',
    recording_id: 'r1',
    speaker_id: '3',
    speaker_name: '王五',
    text: '前端性能优化这块，我觉得可以先从代码分割和懒加载入手，效果会比较明显。',
    start_time: 45,
    end_time: 55,
    confidence: 0.87,
    emotion: 'happy',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

export default function RecordingDetailScreen() {
  const theme = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const api = useApi();

  const [recording, setRecording] = useState<RecordingDetail>(MOCK_RECORDING);
  const [utterances, setUtterances] = useState<Utterance[]>(MOCK_UTTERANCES);
  const [loading, setLoading] = useState(true);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  useEffect(() => {
    // Simulate API loading
    const timer = setTimeout(() => {
      setRecording({ ...MOCK_RECORDING, id });
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
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

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

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      <Appbar.Header elevated>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content
          title={recording.title || '录音详情'}
          titleStyle={styles.headerTitle}
        />
        <Appbar.Action
          icon="dots-vertical"
          onPress={() => showSnackbar('更多选项')}
        />
      </Appbar.Header>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Recording Info Card */}
        <Surface style={styles.infoCard} elevation={1}>
          <View style={styles.infoRow}>
            <View style={styles.infoItem}>
              <MaterialCommunityIcons
                name="calendar"
                size={18}
                color={theme.colors.primary}
              />
              <Text variant="bodySmall" style={styles.infoText}>
                {formatDate(recording.created_at)}
              </Text>
            </View>
            <View style={styles.infoItem}>
              <MaterialCommunityIcons
                name="clock-outline"
                size={18}
                color={theme.colors.primary}
              />
              <Text variant="bodySmall" style={styles.infoText}>
                {formatDuration(recording.duration)}
              </Text>
            </View>
          </View>
          {recording.location && (
            <View style={[styles.infoItem, { marginTop: 4 }]}>
              <MaterialCommunityIcons
                name="map-marker"
                size={18}
                color={theme.colors.primary}
              />
              <Text variant="bodySmall" style={styles.infoText}>
                {recording.location}
              </Text>
            </View>
          )}
          <View style={styles.infoRow}>
            <Chip icon="account-voice" compact style={styles.infoChip}>
              {recording.speaker_count} 位说话人
            </Chip>
            <Chip icon="message-text" compact style={styles.infoChip}>
              {recording.utterance_count} 条对话
            </Chip>
            {recording.is_meeting && (
              <Chip icon="office-building" compact style={styles.infoChip}>
                会议
              </Chip>
            )}
          </View>
        </Surface>

        {/* AI Summary Card */}
        {recording.ai_summary && (
          <Card style={styles.summaryCard} mode="elevated">
            <Card.Content>
              <View style={styles.cardHeader}>
                <MaterialCommunityIcons
                  name="brain"
                  size={20}
                  color={theme.colors.primary}
                />
                <Text variant="titleSmall" style={styles.cardTitle}>
                  AI 摘要
                </Text>
              </View>
              <Text
                variant="bodyMedium"
                style={{ lineHeight: 22, color: theme.colors.onSurfaceVariant }}
              >
                {recording.ai_summary}
              </Text>

              {recording.topics && recording.topics.length > 0 && (
                <View style={styles.topicsRow}>
                  {recording.topics.map((topic) => (
                    <Chip
                      key={topic}
                      compact
                      style={styles.topicChip}
                      textStyle={{ fontSize: 11 }}
                    >
                      {topic}
                    </Chip>
                  ))}
                </View>
              )}
            </Card.Content>
          </Card>
        )}

        {/* Meeting Minutes Card */}
        {recording.is_meeting && recording.meeting_minutes && (
          <Card style={styles.minutesCard} mode="elevated">
            <Card.Content>
              <View style={styles.cardHeader}>
                <MaterialCommunityIcons
                  name="file-document"
                  size={20}
                  color={theme.colors.primary}
                />
                <Text variant="titleSmall" style={styles.cardTitle}>
                  会议纪要
                </Text>
              </View>
              <Text
                variant="bodyMedium"
                style={{
                  lineHeight: 22,
                  color: theme.colors.onSurfaceVariant,
                  fontFamily: 'monospace',
                }}
              >
                {recording.meeting_minutes}
              </Text>
            </Card.Content>
          </Card>
        )}

        <Divider style={styles.sectionDivider} />

        {/* Utterances Section */}
        <View style={styles.utterancesSection}>
          <Text variant="titleSmall" style={styles.sectionTitle}>
            对话片段
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
                暂无对话片段
              </Text>
            </View>
          ) : (
            utterances.map((utterance) => (
              <UtteranceBubble
                key={utterance.id}
                utterance={utterance}
                speakerName={utterance.speaker_name || `未知-${utterance.speaker_id.slice(-4)}`}
                isMaster={utterance.speaker_id === 'me'}
              />
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
  infoCard: {
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderRadius: 12,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 12,
  },
  infoItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  infoText: {
    marginLeft: 4,
    color: '#666',
  },
  infoChip: {
    marginTop: 8,
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
  topicsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
    gap: 6,
  },
  topicChip: {
    backgroundColor: '#6200ee15',
  },
  minutesCard: {
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
  },
  sectionDivider: {
    marginVertical: 16,
    marginHorizontal: 16,
  },
  utterancesSection: {
    paddingHorizontal: 4,
  },
  sectionTitle: {
    fontWeight: '600',
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
});
