import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
} from 'react-native';
import {
  Appbar,
  Searchbar,
  Menu,
  Button,
  Divider,
  Snackbar,
  Text,
  useTheme,
} from 'react-native-paper';
import { useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import SpeakerCard from '../../components/SpeakerCard';
import { useApi } from '../../hooks/useApi';
import { Speaker } from '../../types';
import { API } from '../../constants';
import { StatusBar } from 'expo-status-bar';

// Mock data for initial display
const MOCK_SPEAKERS: Speaker[] = [
  {
    id: '1',
    name: '张三',
    relationship: '同事',
    voiceprint_count: 12,
    total_duration: 3600,
    utterance_count: 45,
    last_met: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    ai_summary: '项目组的资深开发工程师，主要负责后端架构设计，经常讨论技术方案。',
  },
  {
    id: '2',
    name: '李四',
    relationship: '朋友',
    voiceprint_count: 8,
    total_duration: 2400,
    utterance_count: 32,
    last_met: new Date(Date.now() - 3 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 60 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 3 * 86400000).toISOString(),
    ai_summary: '大学同学，经常一起打篮球和讨论投资。最近在考虑换工作。',
  },
  {
    id: '3',
    name: '王五',
    relationship: '家人',
    voiceprint_count: 20,
    total_duration: 7200,
    utterance_count: 120,
    last_met: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date(Date.now() - 90 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    ai_summary: '父亲，退休教师。喜欢讨论历史和政治，经常提醒注意身体。',
  },
  {
    id: '4',
    name: '赵六',
    relationship: '领导',
    voiceprint_count: 5,
    total_duration: 1800,
    utterance_count: 28,
    last_met: new Date(Date.now() - 7 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 45 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    ai_summary: '部门总监，关注项目进度和团队建设。要求每周汇报工作进展。',
  },
  {
    id: '5',
    name: '',
    relationship: '陌生人',
    voiceprint_count: 2,
    total_duration: 300,
    utterance_count: 8,
    last_met: new Date(Date.now() - 14 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 14 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 14 * 86400000).toISOString(),
    ai_summary: '咖啡店偶遇的陌生人，讨论了天气和附近的美食推荐。',
  },
];

const RELATIONSHIP_FILTERS = ['全部', '家人', '朋友', '同事', '领导', '客户', '陌生人', '其他'];

export default function SpeakersScreen() {
  const theme = useTheme();
  const router = useRouter();
  const api = useApi();

  const [speakers, setSpeakers] = useState<Speaker[]>(MOCK_SPEAKERS);
  const [filteredSpeakers, setFilteredSpeakers] = useState<Speaker[]>(MOCK_SPEAKERS);
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [menuVisible, setMenuVisible] = useState(false);
  const [activeFilter, setActiveFilter] = useState('全部');
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Filter speakers based on search and relationship filter
  useEffect(() => {
    let filtered = speakers;

    // Apply relationship filter
    if (activeFilter !== '全部') {
      filtered = filtered.filter(
        (s) => (s.relationship || '陌生人') === activeFilter
      );
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (s) =>
          (s.name || `未知-${s.id.slice(-4)}`).toLowerCase().includes(query) ||
          (s.relationship || '').toLowerCase().includes(query) ||
          (s.ai_summary || '').toLowerCase().includes(query)
      );
    }

    setFilteredSpeakers(filtered);
  }, [searchQuery, activeFilter, speakers]);

  // Fetch speakers from API
  const fetchSpeakers = useCallback(async () => {
    const data = await api.get<Speaker[]>(API.ENDPOINTS.SPEAKERS, {
      user_id: 'default_user',
    });
    if (data) {
      setSpeakers(data);
      showSnackbar('人物列表已更新');
    }
  }, [api]);

  // Pull to refresh
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchSpeakers();
    setRefreshing(false);
  }, [fetchSpeakers]);

  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  const handleSpeakerPress = useCallback(
    (speakerId: string) => {
      router.push(`/speaker/${speakerId}`);
    },
    [router]
  );

  const handleSpeakerLongPress = useCallback((speaker: Speaker) => {
    // Could show options dialog for edit/delete
    showSnackbar(`长按了 ${speaker.name || `未知-${speaker.id.slice(-4)}`}`);
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: Speaker }) => (
      <SpeakerCard
        speaker={item}
        onPress={() => handleSpeakerPress(item.id)}
        onLongPress={() => handleSpeakerLongPress(item)}
      />
    ),
    [handleSpeakerPress, handleSpeakerLongPress]
  );

  const keyExtractor = useCallback((item: Speaker) => item.id, []);

  const ListEmptyComponent = useCallback(
    () => (
      <View style={styles.emptyContainer}>
        <MaterialCommunityIcons
          name="account-search"
          size={64}
          color={theme.colors.outline}
        />
        <Text
          variant="bodyLarge"
          style={[styles.emptyText, { color: theme.colors.onSurfaceVariant }]}
        >
          {searchQuery || activeFilter !== '全部'
            ? '没有找到匹配的人物'
            : '还没有记录到任何人物'}
        </Text>
        <Text
          variant="bodySmall"
          style={{ color: theme.colors.outline, marginTop: 4 }}
        >
          {searchQuery || activeFilter !== '全部'
            ? '尝试调整搜索条件或筛选器'
            : '开始录音后，系统会自动识别说话人'}
        </Text>
      </View>
    ),
    [searchQuery, activeFilter, theme]
  );

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      {/* App Bar */}
      <Appbar.Header elevated>
        <Appbar.Content title="人物库" titleStyle={styles.headerTitle} />
        <Menu
          visible={menuVisible}
          onDismiss={() => setMenuVisible(false)}
          anchor={
            <Appbar.Action
              icon="filter-variant"
              onPress={() => setMenuVisible(true)}
            />
          }
        >
          {RELATIONSHIP_FILTERS.map((filter) => (
            <Menu.Item
              key={filter}
              onPress={() => {
                setActiveFilter(filter);
                setMenuVisible(false);
              }}
              title={filter}
              leadingIcon={activeFilter === filter ? 'check' : undefined}
            />
          ))}
        </Menu>
      </Appbar.Header>

      {/* Search Bar */}
      <Searchbar
        placeholder="搜索姓名、关系..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={[styles.searchBar, { backgroundColor: theme.colors.surfaceVariant }]}
        inputStyle={styles.searchInput}
        iconColor={theme.colors.onSurfaceVariant}
        clearIcon="close-circle"
      />

      {/* Active Filter Chip */}
      {activeFilter !== '全部' && (
        <View style={styles.filterChipContainer}>
          <Button
            mode="outlined"
            compact
            onPress={() => setActiveFilter('全部')}
            icon="close"
            style={styles.filterChip}
          >
            {activeFilter}
          </Button>
        </View>
      )}

      {/* Results count */}
      <Text
        variant="labelSmall"
        style={[styles.resultsCount, { color: theme.colors.onSurfaceVariant }]}
      >
        共 {filteredSpeakers.length} 位人物
      </Text>

      <Divider />

      {/* Speakers List */}
      <FlatList
        data={filteredSpeakers}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={ListEmptyComponent}
        ItemSeparatorComponent={() => <View style={{ height: 0 }} />}
      />

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
  searchBar: {
    marginHorizontal: 16,
    marginVertical: 8,
    borderRadius: 12,
    height: 44,
  },
  searchInput: {
    fontSize: 15,
  },
  filterChipContainer: {
    paddingHorizontal: 16,
    marginBottom: 4,
  },
  filterChip: {
    alignSelf: 'flex-start',
    borderRadius: 16,
  },
  resultsCount: {
    paddingHorizontal: 20,
    paddingVertical: 4,
  },
  listContent: {
    paddingTop: 8,
    paddingBottom: 20,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 80,
    paddingHorizontal: 40,
  },
  emptyText: {
    marginTop: 16,
    fontWeight: '500',
  },
});
