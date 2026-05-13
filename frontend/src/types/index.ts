// ==================== Speaker Types ====================

export interface Speaker {
  id: string;
  name: string;
  avatar_url?: string;
  relationship?: string;
  bio?: string;
  voiceprint_count: number;
  total_duration: number; // seconds
  last_met?: string; // ISO date
  utterance_count: number;
  created_at: string;
  updated_at: string;
  ai_summary?: string;
}

export interface SpeakerDetail extends Speaker {
  events: SpeakerEvent[];
  voiceprints: Voiceprint[];
}

export interface SpeakerEvent {
  id: string;
  type: 'meeting' | 'conversation' | 'note' | 'milestone';
  title: string;
  description?: string;
  timestamp: string;
  recording_id?: string;
}

export interface Voiceprint {
  id: string;
  created_at: string;
  sample_duration: number;
  is_active: boolean;
}

// ==================== Utterance Types ====================

export interface Utterance {
  id: string;
  recording_id: string;
  speaker_id: string;
  speaker_name?: string;
  text: string;
  start_time: number; // seconds from recording start
  end_time: number;
  confidence: number;
  emotion?: 'happy' | 'neutral' | 'sad' | 'angry';
  created_at: string;
}

// ==================== Recording Types ====================

export interface Recording {
  id: string;
  title?: string;
  duration: number; // seconds
  file_path?: string;
  file_size?: number;
  location?: string;
  latitude?: number;
  longitude?: number;
  is_meeting: boolean;
  is_flash_memo: boolean;
  is_processing: boolean;
  is_paused: boolean;
  utterance_count: number;
  speaker_count: number;
  ai_summary?: string;
  topics?: string[];
  meeting_minutes?: string;
  created_at: string;
  updated_at: string;
}

export interface RecordingDetail extends Recording {
  utterances: Utterance[];
  speakers: Speaker[];
}

// ==================== Chat Types ====================

export interface ChatSession {
  id: string;
  title: string;
  message_count: number;
  last_message_at: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SearchResult[];
  created_at: string;
}

// ==================== Search Types ====================

export interface SearchResult {
  id: string;
  utterance_id: string;
  text: string;
  speaker_name: string;
  speaker_id: string;
  recording_id: string;
  recording_time: string;
  similarity: number;
  context_before?: string;
  context_after?: string;
}

// ==================== App Settings Types ====================

export interface AppSettings {
  userId: string;
  apiBaseUrl: string;
  webhookUrl?: string;
  webhookType?: 'feishu' | 'dingtalk' | 'custom';
  permissions: {
    microphone: boolean;
    location: boolean;
    calendar: boolean;
    notifications: boolean;
  };
  theme: 'light' | 'dark' | 'system';
}

// ==================== Recording Status ====================

export type RecordingStatus = 'idle' | 'listening' | 'recording' | 'analyzing' | 'paused';

// ==================== Emotion Map ====================

export const EmotionEmoji: Record<string, string> = {
  happy: '😊',
  neutral: '😐',
  sad: '😔',
  angry: '😠',
};

export const StatusColor: Record<string, string> = {
  listening: '#2196F3',
  recording: '#F44336',
  analyzing: '#FFC107',
  idle: '#9E9E9E',
  paused: '#FF9800',
};
