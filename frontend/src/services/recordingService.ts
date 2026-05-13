/**
 * RecordingService - 底层录音服务类（单例模式）
 *
 * 封装 Expo AV 的音频录制功能，提供：
 * - 音频模式设置
 * - 权限请求
 * - Android 前台服务管理
 * - 短录音（VAD 检测）
 * - 正式录音（分段录制）
 * - 音频文件上传到后端
 *
 * 兼容 Expo Go 和原生环境：前台服务模块采用 try-catch 延迟加载，
 * 在 Expo Go 中不可用时会优雅降级。
 */
import { Audio, AudioMode } from 'expo-av';
import { Platform } from 'react-native';

// ------------------------------------------------------------------
// 延迟加载前台服务模块，兼容 Expo Go（无原生模块的环境）
// ------------------------------------------------------------------
let ForegroundService: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  ForegroundService = require('@supersami/rn-foreground-service').default;
} catch (e) {
  console.warn(
    '[RecordingService] @supersami/rn-foreground-service not available. ' +
      'Foreground service will be disabled (expected in Expo Go).'
  );
}

// ------------------------------------------------------------------
// 类型定义
// ------------------------------------------------------------------

/** 音频上传接口的响应结构 */
export interface UploadResponse {
  /** 后端返回的转写文本 */
  transcript?: string;
  /** 检测到的说话人列表 */
  speakers?: Array<{ id: string; name: string }>;
  /** 本次片段的最近语句 */
  utterances?: Array<{
    id: string;
    text: string;
    speaker: string;
    time: string;
  }>;
  /** 后端返回的错误信息 */
  error?: string;
  /** 任意额外字段 */
  [key: string]: any;
}

/** 短录音采样结果（VAD 用） */
export interface ShortRecordingResult {
  /** 录音实例 */
  recording: Audio.Recording;
  /** 录音状态（包含 metering 等） */
  status: Audio.RecordingStatus;
}

// ------------------------------------------------------------------
// RecordingService 类
// ------------------------------------------------------------------

class RecordingService {
  /** 当前持有的 Recording 实例 */
  private recording: Audio.Recording | null = null;

  /** 是否正在录音的标志 */
  private _isRecording = false;

  /** API 基础地址，从环境变量读取 */
  private readonly apiBaseUrl: string;

  constructor() {
    this.apiBaseUrl =
      process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
  }

  // ================================================================
  //  Getter
  // ================================================================

  /** 当前是否正在录音 */
  get isCurrentlyRecording(): boolean {
    return this._isRecording;
  }

  // ================================================================
  //  音频模式 & 权限
  // ================================================================

  /**
   * 设置音频会话模式，确保在 iOS/Android 上均可正常录音并在后台保持活跃。
   *
   * @throws 当 Expo AV 无法设置音频模式时抛出异常。
   */
  async setupAudio(): Promise<void> {
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true, // iOS 允许录音
      playsInSilentModeIOS: true, // iOS 静音模式下继续播放/录制
      staysActiveInBackground: true, // 后台保持活跃（配合前台服务）
      shouldDuckAndroid: true, // Android 降低其他应用音量
      playThroughEarpieceAndroid: false, // Android 使用扬声器而非听筒
    });
  }

  /**
   * 请求麦克风录音权限。
   *
   * @returns `true` 如果用户授予了权限。
   */
  async requestPermissions(): Promise<boolean> {
    const { status } = await Audio.requestPermissionsAsync();
    return status === 'granted';
  }

  /**
   * 检查当前麦克风权限状态（不弹窗）。
   *
   * @returns `true` 如果已经获得权限。
   */
  async checkPermissions(): Promise<boolean> {
    const { status } = await Audio.getPermissionsAsync();
    return status === 'granted';
  }

  // ================================================================
  //  Android 前台服务
  // ================================================================

  /**
   * 启动 Android 前台服务通知。
   * 在 Expo Go 中（无原生模块）会自动静默跳过。
   *
   * @throws 仅当原生模块存在但启动失败时抛出。
   */
  async startForegroundService(): Promise<void> {
    if (Platform.OS !== 'android' || !ForegroundService) {
      return;
    }
    try {
      await ForegroundService.startService({
        id: 1,
        title: 'AILife 正在监听',
        message: '实时分析周围环境声音…',
        icon: 'ic_launcher',
        button: false, // 不在通知上显示按钮
        buttonText: '',
        buttonOnPress: '',
      });
    } catch (err) {
      console.error('[RecordingService] startForegroundService failed:', err);
      throw err;
    }
  }

  /**
   * 停止 Android 前台服务通知。
   * 在 Expo Go 中会自动静默跳过。
   */
  async stopForegroundService(): Promise<void> {
    if (Platform.OS !== 'android' || !ForegroundService) {
      return;
    }
    try {
      await ForegroundService.stopService();
    } catch (err) {
      console.error('[RecordingService] stopForegroundService failed:', err);
      // 停止服务失败不应阻塞主流程
    }
  }

  // ================================================================
  //  录音控制
  // ================================================================

  /**
   * 创建一段短录音（1.5 秒），用于 VAD 音量检测。
   * 录音结束后会自动 stopAndUnloadAsync()，调用方无需手动清理。
   *
   * @param sampleMs - 采样时长（毫秒），默认 1500ms。
   * @returns 包含 recording 实例和最终 status 的对象。
   * @throws 当 Expo AV 创建或停止录音失败时抛出。
   */
  async createShortRecording(
    sampleMs: number = 1500
  ): Promise<ShortRecordingResult> {
    const { recording } = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );

    // 等待指定的采样时长
    await new Promise((resolve) => setTimeout(resolve, sampleMs));

    const status = await recording.getStatusAsync();
    await recording.stopAndUnloadAsync();

    return { recording, status };
  }

  /**
   * 开始正式录音（长段录音，由调用方控制停止时机）。
   *
   * @returns 创建的 Recording 实例。
   * @throws 当已有录音正在进行，或 Expo AV 创建失败时抛出。
   */
  async startFullRecording(): Promise<Audio.Recording> {
    if (this._isRecording && this.recording) {
      throw new Error('Recording already in progress');
    }

    // 确保先清理之前的实例
    await this.cleanup();

    const { recording } = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );

    this.recording = recording;
    this._isRecording = true;

    return recording;
  }

  /**
   * 停止当前录音并返回音频文件的本地 URI。
   *
   * @returns 音频文件的本地文件 URI；如果没有正在进行的录音则返回 `null`。
   * @throws 当 stopAndUnloadAsync 失败时抛出。
   */
  async stopRecording(): Promise<string | null> {
    if (!this.recording || !this._isRecording) {
      return null;
    }

    const uri = this.recording.getURI();
    await this.recording.stopAndUnloadAsync();

    this.recording = null;
    this._isRecording = false;

    return uri;
  }

  /**
   * 强制清理当前录音实例（用于紧急停止或组件卸载时）。
   */
  async cleanup(): Promise<void> {
    try {
      if (this.recording) {
        const status = await this.recording.getStatusAsync();
        if (status.isRecording) {
          await this.recording.stopAndUnloadAsync();
        } else {
          await this.recording.unloadAsync();
        }
      }
    } catch (err) {
      console.warn('[RecordingService] cleanup warning:', err);
    } finally {
      this.recording = null;
      this._isRecording = false;
    }
  }

  // ================================================================
  //  音频上传
  // ================================================================

  /**
   * 将本地音频文件上传到后端 /upload/ 接口。
   *
   * @param uri - 本地音频文件的 URI（file://...）。
   * @param userId - 当前用户 ID。
   * @param isMeetingMode - 是否为会议模式（多人对话），默认 `false`。
   * @returns 后端返回的 JSON 数据。
   * @throws 当网络请求失败或返回非 2xx 状态时抛出。
   */
  async uploadAudio(
    uri: string,
    userId: string,
    isMeetingMode: boolean = false
  ): Promise<UploadResponse> {
    if (!this.apiBaseUrl) {
      throw new Error(
        'EXPO_PUBLIC_API_URL is not set. Please configure your environment.'
      );
    }

    const formData = new FormData();
    formData.append('file', {
      uri,
      name: 'recording.m4a',
      type: 'audio/m4a',
    } as any);
    formData.append('user_id', userId);
    formData.append('is_meeting_mode', String(isMeetingMode));

    const response = await fetch(`${this.apiBaseUrl}/upload/`, {
      method: 'POST',
      body: formData,
      headers: {
        // React Native 会在 FormData 时自动设置正确的 boundary，
        // 显式设置 Content-Type 反而可能导致 boundary 错误，因此不设置。
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(
        `Upload failed (${response.status} ${response.statusText}): ${text}`
      );
    }

    return (await response.json()) as UploadResponse;
  }
}

// ------------------------------------------------------------------
// 导出单例
// ------------------------------------------------------------------

export default new RecordingService();
