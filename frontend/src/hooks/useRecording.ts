/**
 * useRecording — 录音逻辑封装核心 Hook
 *
 * 管理整个录音生命周期，包含：
 * - 麦克风权限请求
 * - VAD（Voice Activity Detection）循环检测：每 2 秒采样 1.5 秒音频，
 *   若音量超过阈值（-40 dB）则自动开始正式录音。
 * - 正式录音：10 秒自动分段，每段结束后自动上传。
 * - Android 前台服务（通过 recordingService）。
 * - 状态管理：isListening / isRecording / isAnalyzing / metering / error。
 *
 * @example
 * ```tsx
 * const {
 *   isListening, isRecording, isAnalyzing, metering, error,
 *   currentSpeakers, recentUtterances,
 *   startListening, stopListening, startRecording, stopAndUpload,
 * } = useRecording('user-123');
 * ```
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import { Audio } from 'expo-av';
import recordingService from '../services/recordingService';

// ------------------------------------------------------------------
// 常量配置
// ------------------------------------------------------------------

/** VAD 音量阈值（dB），超过此值判定为检测到语音 */
const VAD_THRESHOLD_DB = -40;

/** VAD 采样时长（毫秒） */
const VAD_SAMPLE_MS = 1500;

/** VAD 检测间隔（毫秒）——两次采样之间的等待时间 */
const VAD_INTERVAL_MS = 2000;

/** 单段录音的最大时长（毫秒），达到后自动分段 */
const RECORDING_SEGMENT_MS = 10000;

/** 连续 VAD 检测失败的最大次数，超过则停止监听（避免无限耗电） */
const MAX_VAD_ERRORS = 10;

// ------------------------------------------------------------------
// 类型定义
// ------------------------------------------------------------------

/** 说话人信息 */
export interface Speaker {
  id: string;
  name: string;
}

/** 最近语句 */
export interface Utterance {
  id: string;
  text: string;
  speaker: string;
  time: string;
}

/** useRecording 的完整状态 */
export interface RecordingState {
  /** 是否处于 VAD 监听状态 */
  isListening: boolean;
  /** 是否正在正式录音 */
  isRecording: boolean;
  /** 是否正在分析（上传/转写中） */
  isAnalyzing: boolean;
  /** 当前检测到的说话人列表 */
  currentSpeakers: Speaker[];
  /** 最近的语句记录 */
  recentUtterances: Utterance[];
  /** 当前音量级别（dB），范围约 -160 ~ 0 */
  metering: number;
  /** 错误信息 */
  error: string | null;
}

/** useRecording 返回的完整 API */
export interface UseRecordingReturn extends RecordingState {
  /** 启动 VAD 监听 */
  startListening: () => Promise<void>;
  /** 停止所有录音和监听 */
  stopListening: () => Promise<void>;
  /** 手动开始正式录音 */
  startRecording: () => Promise<void>;
  /** 停止当前录音并上传 */
  stopAndUpload: () => Promise<void>;
}

// ------------------------------------------------------------------
// 辅助函数
// ------------------------------------------------------------------

/**
 * 将 Expo AV 的 metering 值转换为 dB。
 * Expo AV 返回的 metering 是 iOS 上的原生值（范围通常 -160 ~ 0），
 * 直接返回即可用于比较。
 */
function normalizeMetering(metering: number | undefined): number {
  if (metering === undefined || metering === null || isNaN(metering)) {
    return -160; // 无声
  }
  return metering;
}

// ------------------------------------------------------------------
// Hook
// ------------------------------------------------------------------

/**
 * @param userId - 当前用户的唯一标识，用于上传音频时关联用户。
 * @returns 录音状态和控制方法。
 */
export function useRecording(userId: string): UseRecordingReturn {
  // ================================================================
  //  状态
  // ================================================================

  const [isListening, setIsListening] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentSpeakers, setCurrentSpeakers] = useState<Speaker[]>([]);
  const [recentUtterances, setRecentUtterances] = useState<Utterance[]>([]);
  const [metering, setMetering] = useState<number>(-160);
  const [error, setError] = useState<string | null>(null);

  // ================================================================
  //  Refs（用于在异步循环中读取最新状态/控制循环取消）
  // ================================================================

  /** 控制 VAD 循环是否继续运行 */
  const isListeningRef = useRef(false);

  /** 当前持有的录音实例 */
  const recordingRef = useRef<Audio.Recording | null>(null);

  /** 分段录音的 timeout ID */
  const segmentTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** VAD 连续失败计数 */
  const vadErrorCountRef = useRef(0);

  /** 组件是否已卸载 */
  const isUnmountedRef = useRef(false);

  // ================================================================
  //  同步 ref 与 state
  // ================================================================

  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

  // ================================================================
  //  清理函数
  // ================================================================

  /**
   * 清除分段录音的定时器。
   */
  const clearSegmentTimeout = useCallback(() => {
    if (segmentTimeoutRef.current) {
      clearTimeout(segmentTimeoutRef.current);
      segmentTimeoutRef.current = null;
    }
  }, []);

  /**
   * 完全停止录音并清理资源（不触发上传）。
   */
  const cleanupRecording = useCallback(async () => {
    clearSegmentTimeout();

    try {
      if (recordingRef.current) {
        const status = await recordingRef.current.getStatusAsync();
        if (status.isRecording) {
          await recordingRef.current.stopAndUnloadAsync();
        }
      }
    } catch (err) {
      console.warn('[useRecording] cleanupRecording warning:', err);
    } finally {
      recordingRef.current = null;
    }
  }, [clearSegmentTimeout]);

  /**
   * 组件卸载时执行全面清理。
   */
  useEffect(() => {
    isUnmountedRef.current = false;
    return () => {
      isUnmountedRef.current = true;
      // 立即标记停止，所有循环将在下一次迭代退出
      isListeningRef.current = false;
      cleanupRecording();
      recordingService.stopForegroundService();
    };
  }, [cleanupRecording]);

  // ================================================================
  //  内部：分段录音 → 上传流程
  // ================================================================

  /**
   * 执行一次完整的“录音 → 停止 → 上传 → 解析结果”流程。
   * 这是 VAD 检测到语音后被调用的核心逻辑。
   */
  const recordAndUpload = useCallback(async () => {
    if (isUnmountedRef.current) return;
    if (isRecording) return; // 已在录音中（理论上不应发生，作为保险）

    // ---- 开始录音 ----
    setIsRecording(true);
    setError(null);
    vadErrorCountRef.current = 0; // 重置 VAD 错误计数

    try {
      const recording = await recordingService.startFullRecording();
      if (isUnmountedRef.current) {
        await recordingService.cleanup();
        return;
      }
      recordingRef.current = recording;

      // ---- 设置 10 秒自动分段 ----
      await new Promise<void>((resolve) => {
        segmentTimeoutRef.current = setTimeout(() => {
          resolve();
        }, RECORDING_SEGMENT_MS);
      });

      // 如果组件已卸载或监听已被停止，不上传
      if (isUnmountedRef.current || !isListeningRef.current) {
        await recordingService.stopRecording();
        setIsRecording(false);
        return;
      }

      // ---- 停止录音 ----
      const uri = await recordingService.stopRecording();
      recordingRef.current = null;
      setIsRecording(false);

      if (!uri) {
        throw new Error('Recording returned empty URI');
      }

      // ---- 上传 & 分析 ----
      setIsAnalyzing(true);

      const result = await recordingService.uploadAudio(uri, userId, false);

      if (isUnmountedRef.current) return;

      // ---- 解析并更新状态 ----
      if (result.speakers && result.speakers.length > 0) {
        setCurrentSpeakers((prev) => {
          const merged = [...prev];
          result.speakers!.forEach((s) => {
            if (!merged.find((m) => m.id === s.id)) {
              merged.push(s);
            }
          });
          return merged;
        });
      }

      if (result.utterances && result.utterances.length > 0) {
        setRecentUtterances((prev) => {
          const incoming = result.utterances!;
          const combined = [...prev, ...incoming];
          // 只保留最近 50 条，防止内存无限增长
          return combined.slice(-50);
        });
      }

      if (result.error) {
        console.warn('[useRecording] Server returned error:', result.error);
      }
    } catch (err: any) {
      if (isUnmountedRef.current) return;
      console.error('[useRecording] recordAndUpload error:', err);
      setError(err?.message ?? '录音或上传过程中发生未知错误');
    } finally {
      recordingRef.current = null;
      setIsRecording(false);
      setIsAnalyzing(false);
      clearSegmentTimeout();
    }
  }, [userId, isRecording, clearSegmentTimeout]);

  // ================================================================
  //  内部：VAD 循环
  // ================================================================

  /**
   * 单次 VAD 采样：录制 1.5 秒音频，读取 metering，判断是否超过阈值。
   *
   * @returns `true` 如果检测到语音（metering > 阈值）。
   */
  const runVadSample = useCallback(async (): Promise<boolean> => {
    try {
      const { status } = await recordingService.createShortRecording(VAD_SAMPLE_MS);

      if (isUnmountedRef.current || !isListeningRef.current) {
        return false;
      }

      // Expo AV 的 status.metering 是 dB 值（-160 ~ 0）
      const db = normalizeMetering(status.metering);
      setMetering(db);

      // 如果超过阈值，判定为有语音活动
      return db > VAD_THRESHOLD_DB;
    } catch (err: any) {
      vadErrorCountRef.current += 1;
      console.warn(
        `[useRecording] VAD sample failed (${vadErrorCountRef.current}/${MAX_VAD_ERRORS}):`,
        err?.message
      );
      return false;
    }
  }, []);

  /**
   * VAD 主循环：每隔 VAD_INTERVAL_MS 执行一次采样，
   * 检测到语音后自动调用 recordAndUpload()。
   */
  const vadLoop = useCallback(async () => {
    vadErrorCountRef.current = 0;

    while (isListeningRef.current && !isUnmountedRef.current) {
      // 如果已经在录音中，等待本次录音完成
      if (recordingRef.current) {
        await new Promise((r) => setTimeout(r, 500));
        continue;
      }

      // ---- 执行 VAD 采样 ----
      const hasVoice = await runVadSample();

      if (isUnmountedRef.current || !isListeningRef.current) break;

      // ---- 连续错误过多，自动停止监听 ----
      if (vadErrorCountRef.current >= MAX_VAD_ERRORS) {
        setError('麦克风连续采样失败，监听已自动停止');
        setIsListening(false);
        break;
      }

      // ---- 检测到语音 → 开始正式录音 ----
      if (hasVoice) {
        await recordAndUpload();
        // 录音上传完成后继续 VAD 循环
      }

      // ---- 间隔等待 ----
      if (isListeningRef.current && !recordingRef.current) {
        await new Promise((r) => setTimeout(r, VAD_INTERVAL_MS));
      }
    }

    // 循环退出时的清理
    if (isUnmountedRef.current) {
      await recordingService.cleanup();
      await recordingService.stopForegroundService();
    }
  }, [runVadSample, recordAndUpload]);

  // ================================================================
  //  公开：startListening
  // ================================================================

  /**
   * 启动 VAD 监听循环。
   *
   * 流程：
   * 1. 请求麦克风权限。
   * 2. 设置音频模式。
   * 3. 启动 Android 前台服务。
   * 4. 进入 VAD 循环（每 2 秒采样 1.5 秒，检测语音活动）。
   */
  const startListening = useCallback(async () => {
    if (isListening) return; // 已在监听中

    setError(null);

    try {
      // 1. 权限
      const hasPermission = await recordingService.requestPermissions();
      if (!hasPermission) {
        setError('麦克风权限被拒绝，请在系统设置中开启');
        return;
      }

      // 2. 音频模式
      await recordingService.setupAudio();

      // 3. Android 前台服务
      await recordingService.startForegroundService();

      // 4. 启动 VAD 循环
      setIsListening(true);
      isListeningRef.current = true;
      vadErrorCountRef.current = 0;

      // 在后台启动 VAD 循环（不阻塞调用方）
      vadLoop();
    } catch (err: any) {
      console.error('[useRecording] startListening error:', err);
      setError(err?.message ?? '启动监听失败');
      setIsListening(false);
      isListeningRef.current = false;
      await recordingService.stopForegroundService();
    }
  }, [isListening, vadLoop]);

  // ================================================================
  //  公开：stopListening
  // ================================================================

  /**
   * 停止所有录音和 VAD 监听。
   *
   * 这会：
   * - 设置 isListening = false，使 VAD 循环在下一次迭代退出。
   * - 停止当前正在进行的录音。
   * - 停止 Android 前台服务。
   * - 清除所有定时器。
   */
  const stopListening = useCallback(async () => {
    isListeningRef.current = false;
    setIsListening(false);
    setIsRecording(false);
    clearSegmentTimeout();

    try {
      await cleanupRecording();
      await recordingService.stopForegroundService();
    } catch (err: any) {
      console.error('[useRecording] stopListening error:', err);
    }
  }, [cleanupRecording, clearSegmentTimeout]);

  // ================================================================
  //  公开：startRecording（手动触发）
  // ================================================================

  /**
   * 手动开始一段正式录音（忽略 VAD，直接录制）。
   * 调用方需要在合适的时机调用 `stopAndUpload()`。
   */
  const startRecording = useCallback(async () => {
    if (isRecording) return;

    setError(null);

    try {
      const hasPermission = await recordingService.checkPermissions();
      if (!hasPermission) {
        const granted = await recordingService.requestPermissions();
        if (!granted) {
          setError('麦克风权限被拒绝');
          return;
        }
      }

      await recordingService.setupAudio();
      const recording = await recordingService.startFullRecording();
      recordingRef.current = recording;
      setIsRecording(true);

      // 同样设置 10 秒自动分段
      segmentTimeoutRef.current = setTimeout(() => {
        // 到时间后自动停止并上传
        stopAndUpload();
      }, RECORDING_SEGMENT_MS);
    } catch (err: any) {
      console.error('[useRecording] startRecording error:', err);
      setError(err?.message ?? '开始录音失败');
    }
  }, [isRecording]);

  // ================================================================
  //  公开：stopAndUpload
  // ================================================================

  /**
   * 停止当前录音并上传到后端。
   *
   * 上传成功后，会自动更新 `currentSpeakers` 和 `recentUtterances`。
   */
  const stopAndUpload = useCallback(async () => {
    if (!recordingRef.current) return;

    clearSegmentTimeout();

    try {
      const uri = await recordingService.stopRecording();
      recordingRef.current = null;
      setIsRecording(false);

      if (!uri) {
        throw new Error('没有可上传的录音');
      }

      setIsAnalyzing(true);

      const result = await recordingService.uploadAudio(uri, userId, false);

      if (result.speakers && result.speakers.length > 0) {
        setCurrentSpeakers((prev) => {
          const merged = [...prev];
          result.speakers!.forEach((s) => {
            if (!merged.find((m) => m.id === s.id)) {
              merged.push(s);
            }
          });
          return merged;
        });
      }

      if (result.utterances && result.utterances.length > 0) {
        setRecentUtterances((prev) => {
          const combined = [...prev, ...result.utterances!];
          return combined.slice(-50);
        });
      }
    } catch (err: any) {
      console.error('[useRecording] stopAndUpload error:', err);
      setError(err?.message ?? '上传录音失败');
    } finally {
      setIsAnalyzing(false);
      recordingRef.current = null;
    }
  }, [userId, clearSegmentTimeout]);

  // ================================================================
  //  返回
  // ================================================================

  return {
    // 状态
    isListening,
    isRecording,
    isAnalyzing,
    currentSpeakers,
    recentUtterances,
    metering,
    error,

    // 控制方法
    startListening,
    stopListening,
    startRecording,
    stopAndUpload,
  };
}
