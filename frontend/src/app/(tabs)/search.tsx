import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import {
  Appbar,
  Searchbar,
  Card,
  Chip,
  Avatar,
  Text,
  Divider,
  Snackbar,
  ActivityIndicator,
  useTheme,
  IconButton,
} from 'react-native-paper';
import { useRouter } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';

import { SearchResult } from '../../types';
import { useApi } from '../../hooks/useApi';
import { API } from '../../constants';

// Mock search results
const MOCK_RESULTS: SearchResult[] = [
  {
    id: '1',
    utterance_id: 'u1',
    text: '我上个月在阿里云看到一个不错的 VPS 方案，2核4G只要99一年',
    speaker_name: '我',
    speaker_id: 'me',
    recording_id: 'r1',
    recording_time: new Date(Date.now() - 30 * 86400000).toISOString(),
    similarity: 0.92,
    context_before: '最近在整理服务器预算',
    context_after: '要不要一起买？',
  },
  {
    id: '2',
    utterance_id: 'u2',
    text: 'VPS 到期了，我在想要不要换个服务商，搬瓦工好像也涨价了',
    speaker_name: '李四',
    speaker_id: '2',
    recording_id: 'r2',
    recording_time: new Date(Date.now() - 20 * 86400000).toISOString(),
    similarity: 0.85,
    context_before: '网站最近有点慢',
    context_after: '你有什么推荐的吗',
  },
  {
    id: '3',
    utterance_id: 'u3',
    text: '我觉得 AWS 的免费额度够用了，先不急着买新的 VPS',
    speaker_name: '张三',
    speaker_id: '1',
    recording_id: 'r3',
    recording_time: new Date(Date.now() - 15 * 86400000).toISOString(),
    similarity: 0.78,
    context_before: '在讨论云服务选型',
    context_after: '等流量上来再考虑付费',
  },
];

const SUGGESTIONS = [
  '我上个月在哪里提到过要换VPS？',
  '张三推荐了哪些技术方案？',
  '上次会议讨论了哪些行动计划？',
  '我和李四讨论了哪些投资话题？',
];

export default function SearchScreen() {
  const theme = useTheme();
  const router = useRouter();
  const api = useApi();
  const searchBarRef = useRef(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Perform semantic search
  const performSearch = useCallback(
    async (query: string) => {
      if (!query.trim()) {
        setResults([]);
        setHasSearched(false);
        return;
      }

      setIsSearching(true);
      setHasSearched(true);

      try {
        const data = await api.get<SearchResult[]>(API.ENDPOINTS.SEARCH, {
          q: query.trim(),
          user_id: 'default_user',
        });

        if (data && data.length > 0) {
          setResults(data);
        } else {
          // Use mock data when API returns empty
          setResults(
            MOCK_RESULTS.filter(
              (r) =>
                r.text.toLowerCase().includes(query.toLowerCase()) ||
                r.similarity > 0.7
            )
          );
        }
      } catch {
        setResults(MOCK_RESULTS);
        showSnackbar('搜索服务暂不可用，显示示例结果');
      } finally {
        setIsSearching(false);
      }
    },
    [api]
  );

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        performSearch(searchQuery);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [searchQuery, performSearch]);

  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  const handleSuggestionPress = useCallback(
    (suggestion: string) => {
      setSearchQuery(suggestion);
      performSearch(suggestion);
    },
    [performSearch]
  );

  const handleResultPress = useCallback(
    (recordingId: string) => {
      router.push(`/recording/${recordingId}`);
    },
    [router]
  );

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (days < 30) return `${Math.floor(days / 7)}周前`;
    if (days < 365) return `${Math.floor(days / 30)}个月前`;
    return `${Math.floor(days / 365)}年前`;
  };

  const renderSuggestion = useCallback(
    ({ item }: { item: string }) => (
      <Chip
        style={styles.suggestionChip}
        onPress={() => handleSuggestionPress(item)}
        textStyle={{ fontSize: 13 }}
        icon="magnify"
      >
        {item.length > 20 ? item.substring(0, 20) + '...' : item}
      </Chip>
    ),
    [handleSuggestionPress]
  );

  const renderResult = useCallback(
    ({ item }: { item: SearchResult }) => (
      <Card
        style={styles.resultCard}
        mode="elevated"
        onPress={() => handleResultPress(item.recording_id)}
      >
        <Card.Content>
          <View style={styles.resultHeader}>
            <View style={styles.speakerRow}>
              <Avatar.Text
                size={28}
                label={item.speaker_name.charAt(0)}
                style={{ backgroundColor: theme.colors.secondaryContainer }}
                color={theme.colors.onSecondaryContainer}
              />
              <Text
                variant="labelMedium"
                style={{ marginLeft: 8, fontWeight: '600' }}
              >
                {item.speaker_name}
              </Text>
            </View>
            <View style={styles.metaRow}>
              <Chip compact style={styles.similarityChip}>
                {Math.round(item.similarity * 100)}% 匹配
              </Chip>
              <Text variant="labelSmall" style={{ color: theme.colors.outline }}>
                {formatTime(item.recording_time)}
              </Text>
            </View>
          </View>

          <Divider style={styles.resultDivider} />

          {item.context_before && (
            <Text
              variant="bodySmall"
              style={{ color: theme.colors.outline, marginBottom: 4 }}
            >
              ...{item.context_before}
            </Text>
          )}

          <Text variant="bodyMedium" style={styles.resultText}>
            {item.text}
          </Text>

          {item.context_after && (
            <Text
              variant="bodySmall"
              style={{ color: theme.colors.outline, marginTop: 4 }}
            >
              {item.context_after}...
            </Text>
          )}
        </Card.Content>
      </Card>
    ),
    [handleResultPress, theme]
  );

  const keyExtractor = useCallback((item: SearchResult) => item.id, []);

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      {/* App Bar */}
      <Appbar.Header elevated>
        <Appbar.Content title="语义检索" titleStyle={styles.headerTitle} />
      </Appbar.Header>

      {/* Search Bar */}
      <Searchbar
        ref={searchBarRef}
        placeholder="我上个月在哪里提到过要换VPS？"
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={[styles.searchBar, { backgroundColor: theme.colors.surfaceVariant }]}
        inputStyle={styles.searchInput}
        iconColor={theme.colors.onSurfaceVariant}
        clearIcon="close-circle"
        autoFocus
      />

      {/* Suggestions */}
      {!hasSearched && (
        <View style={styles.suggestionsContainer}>
          <Text
            variant="labelLarge"
            style={[styles.suggestionsTitle, { color: theme.colors.onSurfaceVariant }]}
          >
            试试这样问
          </Text>
          <FlatList
            data={SUGGESTIONS}
            renderItem={renderSuggestion}
            keyExtractor={(item) => item}
            numColumns={1}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.suggestionsList}
          />
        </View>
      )}

      {/* Loading */}
      {isSearching && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator animating size="large" color={theme.colors.primary} />
          <Text
            variant="bodyMedium"
            style={{ color: theme.colors.onSurfaceVariant, marginTop: 12 }}
          >
            AI 正在分析你的语义...
          </Text>
        </View>
      )}

      {/* Results */}
      {!isSearching && hasSearched && (
        <>
          <Text
            variant="labelSmall"
            style={[styles.resultsCount, { color: theme.colors.onSurfaceVariant }]}
          >
            找到 {results.length} 条相关结果
          </Text>

          {results.length === 0 ? (
            <View style={styles.emptyContainer}>
              <MaterialCommunityIcons
                name="text-search"
                size={64}
                color={theme.colors.outline}
              />
              <Text
                variant="bodyLarge"
                style={[styles.emptyText, { color: theme.colors.onSurfaceVariant }]}
              >
                没有找到相关结果
              </Text>
              <Text
                variant="bodySmall"
                style={{ color: theme.colors.outline, marginTop: 4 }}
              >
                尝试换个说法或检查是否有相关录音
              </Text>
            </View>
          ) : (
            <FlatList
              data={results}
              renderItem={renderResult}
              keyExtractor={keyExtractor}
              contentContainerStyle={styles.resultsList}
              showsVerticalScrollIndicator={false}
            />
          )}
        </>
      )}

      {/* Snackbar */}
      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
      >
        {snackbarMessage}
      </Snackbar>
    </KeyboardAvoidingView>
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
    height: 48,
  },
  searchInput: {
    fontSize: 15,
  },
  suggestionsContainer: {
    paddingHorizontal: 16,
    marginTop: 8,
  },
  suggestionsTitle: {
    fontWeight: '600',
    marginBottom: 8,
  },
  suggestionsList: {
    paddingBottom: 16,
  },
  suggestionChip: {
    marginVertical: 4,
    alignSelf: 'flex-start',
    borderRadius: 8,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resultsCount: {
    paddingHorizontal: 20,
    paddingVertical: 4,
  },
  resultsList: {
    paddingTop: 8,
    paddingBottom: 20,
    paddingHorizontal: 16,
  },
  resultCard: {
    marginBottom: 10,
    borderRadius: 12,
  },
  resultHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  speakerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  similarityChip: {
    marginRight: 8,
    height: 24,
  },
  resultDivider: {
    marginVertical: 8,
  },
  resultText: {
    lineHeight: 20,
    fontWeight: '500',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
  },
  emptyText: {
    marginTop: 16,
    fontWeight: '500',
  },
});
