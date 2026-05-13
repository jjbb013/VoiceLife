import { Platform } from 'react-native';

export const COLORS = {
  primary: '#6200ee',
  primaryDark: '#3700b3',
  accent: '#03dac6',
  accentDark: '#018786',
  error: '#B00020',
  background: '#f6f6f6',
  surface: '#ffffff',
  surfaceDark: '#121212',
  surfaceDarkElevated: '#1e1e1e',
  text: '#000000',
  textDark: '#ffffff',
  textSecondary: '#757575',
  textSecondaryDark: '#a0a0a0',
  border: '#e0e0e0',
  borderDark: '#2c2c2c',
  success: '#4CAF50',
  warning: '#FFC107',
  info: '#2196F3',
};

export const API = {
  BASE_URL: 'http://localhost:8000',
  ENDPOINTS: {
    SPEAKERS: '/speakers',
    SPEAKER_DETAIL: (id: string) => `/speakers/${id}`,
    SPEAKER_UTTERANCES: (id: string) => `/utterances/speaker/${id}`,
    RECORDINGS: '/recordings',
    RECORDING_DETAIL: (id: string) => `/recordings/${id}`,
    RECORDING_UTTERANCES: (id: string) => `/utterances/recording/${id}`,
    CHAT: '/chat',
    CHAT_SESSIONS: '/chat/sessions',
    CHAT_MESSAGES: (id: string) => `/chat/sessions/${id}/messages`,
    SEARCH: '/search',
    WEBHOOK: '/settings/webhook',
  },
};

export const STORAGE_KEYS = {
  USER_ID: '@ailife_user_id',
  API_URL: '@ailife_api_url',
  WEBHOOK_URL: '@ailife_webhook_url',
  WEBHOOK_TYPE: '@ailife_webhook_type',
  THEME: '@ailife_theme',
  PERMISSIONS: '@ailife_permissions',
};

export const APP_INFO = {
  NAME: 'AILife',
  VERSION: '1.0.0',
  BUILD_NUMBER: '1',
  DESCRIPTION: 'AI 驱动的智能生活记录助手',
  AUTHOR: 'AILife Team',
};

export const RECORDING_CONFIG = {
  MAX_DURATION: 3600, // 1 hour in seconds
  SAMPLE_RATE: 16000,
  CHANNELS: 1,
  BIT_DEPTH: 16,
  FLASH_MEMO_MAX_DURATION: 60, // 1 minute for flash memo
};

export const DEFAULT_SETTINGS = {
  userId: `user_${Date.now()}`,
  apiBaseUrl: API.BASE_URL,
  theme: 'system' as const,
  permissions: {
    microphone: false,
    location: false,
    calendar: false,
    notifications: false,
  },
};

export const RELATIONSHIP_OPTIONS = [
  '家人',
  '朋友',
  '同事',
  '领导',
  '客户',
  '陌生人',
  '其他',
];

export const TAB_BAR_HEIGHT = Platform.OS === 'ios' ? 88 : 60;
export const HEADER_HEIGHT = 56;
