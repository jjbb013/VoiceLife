import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Dimensions,
} from 'react-native';
import {
  Appbar,
  TextInput,
  IconButton,
  Card,
  Avatar,
  Text,
  Divider,
  Snackbar,
  ActivityIndicator,
  useTheme,
  Menu,
} from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { ChatMessage, ChatSession } from '../../types';
import { useApi } from '../../hooks/useApi';
import { API } from '../../constants';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

// Mock data
const MOCK_SESSIONS: ChatSession[] = [
  {
    id: '1',
    title: '默认会话',
    message_count: 12,
    last_message_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
];

const MOCK_MESSAGES: ChatMessage[] = [
  {
    id: '1',
    session_id: '1',
    role: 'assistant',
    content: '你好！我是 AILife AI 助手。你可以问我关于你的录音记录、人物关系、日程安排等问题。',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: '2',
    session_id: '1',
    role: 'user',
    content: '我最近和张三讨论了什么？',
    created_at: new Date(Date.now() - 3000000).toISOString(),
  },
  {
    id: '3',
    session_id: '1',
    role: 'assistant',
    content: '根据最近的录音记录，你和张三在昨天讨论了以下内容：\n\n1. 后端架构的技术选型问题\n2. 微服务拆分的粒度把握\n3. 数据库迁移的方案评估\n\n张三比较倾向于使用 PostgreSQL，并建议先做一个概念验证（POC）。',
    sources: [],
    created_at: new Date(Date.now() - 2400000).toISOString(),
  },
];

export default function ChatScreen() {
  const theme = useTheme();
  const router = useRouter();
  const api = useApi();
  const flatListRef = useRef<FlatList>(null);

  const [messages, setMessages] = useState<ChatMessage[]>(MOCK_MESSAGES);
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [currentSession] = useState<ChatSession>(MOCK_SESSIONS[0]);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [menuVisible, setMenuVisible] = useState(false);

  // Scroll to bottom on new message
  useEffect(() => {
    if (messages.length > 0 && flatListRef.current) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages]);

  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  const sendMessage = useCallback(async () => {
    if (!inputText.trim() || isSending) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      session_id: currentSession.id,
      role: 'user',
      content: inputText.trim(),
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText('');
    setIsSending(true);

    try {
      // API call
      const response = await api.post<ChatMessage>(API.ENDPOINTS.CHAT, {
        session_id: currentSession.id,
        message: userMessage.content,
        user_id: 'default_user',
      });

      if (response) {
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          session_id: currentSession.id,
          role: 'assistant',
          content: response.content || '收到你的消息了，让我查一下相关记录...',
          sources: response.sources,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        // Mock response when API fails
        const mockResponse: ChatMessage = {
          id: (Date.now() + 1).toString(),
          session_id: currentSession.id,
          role: 'assistant',
          content: `关于「${userMessage.content}」，根据你的录音记录，我找到了以下信息：\n\n你在最近的对话中提到了这个话题。具体的细节还需要我进一步检索。你可以尝试更具体地描述你想了解的内容。`,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, mockResponse]);
      }
    } catch {
      showSnackbar('发送消息失败，请重试');
    } finally {
      setIsSending(false);
    }
  }, [inputText, isSending, currentSession, api, showSnackbar]);

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderMessage = useCallback(
    ({ item }: { item: ChatMessage }) => {
      const isUser = item.role === 'user';

      return (
        <View
          style={[
            styles.messageContainer,
            isUser ? styles.userMessage : styles.assistantMessage,
          ]}
        >
          {!isUser && (
            <Avatar.Icon
              size={32}
              icon="robot"
              style={[styles.avatar, { backgroundColor: theme.colors.primaryContainer }]}
              color={theme.colors.onPrimaryContainer}
            />
          )}

          <View style={styles.messageContent}>
            {!isUser && (
              <Text variant="labelSmall" style={[styles.senderLabel, { color: theme.colors.primary }]}>
                AI 助手
              </Text>
            )}

            <Card
              style={[
                styles.messageBubble,
                isUser
                  ? { backgroundColor: theme.colors.primaryContainer }
                  : { backgroundColor: theme.colors.surfaceVariant },
              ]}
              mode="outlined"
              outlineColor="transparent"
            >
              <Card.Content style={styles.bubbleContent}>
                <Text
                  variant="bodyMedium"
                  style={{
                    color: isUser
                      ? theme.colors.onPrimaryContainer
                      : theme.colors.onSurfaceVariant,
                    lineHeight: 20,
                  }}
                >
                  {item.content}
                </Text>
              </Card.Content>
            </Card>

            <Text variant="labelSmall" style={[styles.timestamp, { color: theme.colors.outline }]}>
              {formatTime(item.created_at)}
            </Text>
          </View>

          {isUser && (
            <Avatar.Icon
              size={32}
              icon="account"
              style={[styles.avatar, { backgroundColor: theme.colors.secondaryContainer }]}
              color={theme.colors.onSecondaryContainer}
            />
          )}
        </View>
      );
    },
    [theme]
  );

  const keyExtractor = useCallback((item: ChatMessage) => item.id, []);

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: theme.colors.background }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      {/* App Bar */}
      <Appbar.Header elevated>
        <Appbar.Content title={currentSession.title} titleStyle={styles.headerTitle} />
        <Menu
          visible={menuVisible}
          onDismiss={() => setMenuVisible(false)}
          anchor={
            <Appbar.Action icon="dots-vertical" onPress={() => setMenuVisible(true)} />
          }
        >
          <Menu.Item
            leadingIcon="history"
            onPress={() => {}}
            title="历史会话"
          />
          <Menu.Item
            leadingIcon="delete-outline"
            onPress={() => {
              setMessages([]);
              setMenuVisible(false);
              showSnackbar('已清空当前会话');
            }}
            title="清空会话"
          />
        </Menu>
      </Appbar.Header>

      {/* Messages List */}
      {messages.length === 0 ? (
        <View style={styles.emptyContainer}>
          <MaterialCommunityIcons
            name="chat-processing-outline"
            size={72}
            color={theme.colors.outline}
          />
          <Text
            variant="bodyLarge"
            style={[styles.emptyText, { color: theme.colors.onSurfaceVariant }]}
          >
            开始和 AI 助手对话
          </Text>
          <Text
            variant="bodySmall"
            style={{ color: theme.colors.outline, marginTop: 4, textAlign: 'center' }}
          >
            询问关于你的录音、人物、日程等任何问题
          </Text>
        </View>
      ) : (
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.messagesList}
          showsVerticalScrollIndicator={false}
        />
      )}

      <Divider />

      {/* Input Area */}
      <View style={[styles.inputContainer, { backgroundColor: theme.colors.elevation.level1 }]}>
        <TextInput
          mode="flat"
          placeholder="输入你的问题..."
          value={inputText}
          onChangeText={setInputText}
          style={[styles.textInput, { backgroundColor: theme.colors.surfaceVariant }]}
          underlineColor="transparent"
          activeUnderlineColor="transparent"
          multiline
          maxLength={500}
          disabled={isSending}
          right={
            <TextInput.Affix
              text={`${inputText.length}/500`}
              textStyle={{ fontSize: 10, color: theme.colors.outline }}
            />
          }
        />
        <IconButton
          icon={isSending ? 'loading' : 'send'}
          size={24}
          iconColor={theme.colors.primary}
          containerColor={theme.colors.primaryContainer}
          onPress={sendMessage}
          disabled={!inputText.trim() || isSending}
          style={styles.sendButton}
        />
      </View>

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
  messagesList: {
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  messageContainer: {
    flexDirection: 'row',
    marginVertical: 6,
    maxWidth: '85%',
  },
  userMessage: {
    alignSelf: 'flex-end',
    flexDirection: 'row',
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
  },
  avatar: {
    marginTop: 4,
  },
  messageContent: {
    flex: 1,
    marginHorizontal: 8,
  },
  senderLabel: {
    marginBottom: 2,
    fontWeight: '600',
  },
  messageBubble: {
    borderRadius: 16,
    minWidth: 60,
  },
  bubbleContent: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  timestamp: {
    marginTop: 2,
    alignSelf: 'flex-end',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 8,
    paddingBottom: Platform.OS === 'ios' ? 20 : 8,
  },
  textInput: {
    flex: 1,
    borderRadius: 20,
    maxHeight: 100,
    minHeight: 44,
    paddingHorizontal: 16,
    paddingTop: 10,
    fontSize: 15,
  },
  sendButton: {
    marginLeft: 8,
    marginBottom: 2,
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
