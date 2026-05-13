/**
 * useNotifications — 通知管理 Hook
 *
 * 封装 Expo Notifications 的功能：
 * - 请求推送/本地通知权限
 * - 显示本地通知
 * - 处理通知点击事件
 * - 支持通知通道管理（Android）
 * - 支持监听接收到的通知
 *
 * @example
 * ```tsx
 * const { showNotification, expoPushToken, permissionStatus } = useNotifications();
 *
 * // 显示一条本地通知
 * await showNotification('录音完成', '音频已成功上传并分析');
 *
 * // 显示带数据的通知
 * await showNotification('新消息', '有人提到了你', { screen: 'Chat', id: '123' });
 * ```
 */
import { useEffect, useCallback, useRef, useState } from 'react';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

// ------------------------------------------------------------------
// 默认通知处理器（应用全局级别）
// ------------------------------------------------------------------

/**
 * 配置 Expo Notifications 的全局处理行为：
 * - 显示 Alert（横幅/弹窗）
 * - 播放声音
 * - 不更新角标数字
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

// ------------------------------------------------------------------
// 类型定义
// ------------------------------------------------------------------

/** 通知数据载荷 */
export interface NotificationData {
  /** 任意键值对数据 */
  [key: string]: any;
}

/** 显示通知的配置选项 */
export interface ShowNotificationOptions {
  /** 副标题（iOS） */
  subtitle?: string;
  /** 通知数据载荷（点击通知时可获取） */
  data?: NotificationData;
  /** 声音名称，默认使用系统提示音 */
  sound?: string | boolean;
  /**
   * 通知触发方式：
   * - `null`（默认）：立即显示
   * - `number`：N 秒后显示
   * - `Date`：指定时间显示
   */
  trigger?: { seconds: number } | Date | null;
}

/** useNotifications 返回的 API */
export interface UseNotificationsReturn {
  /** Expo 推送令牌（远程推送用） */
  expoPushToken: string | null;
  /** 当前权限状态 */
  permissionStatus: Notifications.NotificationPermissionsStatus | null;
  /** 是否正在请求权限 */
  isRequesting: boolean;
  /** 显示一条本地通知 */
  showNotification: (
    title: string,
    body: string,
    options?: ShowNotificationOptions
  ) => Promise<string | undefined>;
  /** 请求通知权限 */
  requestPermission: () => Promise<boolean>;
  /** 取消所有待发送的本地通知 */
  cancelAllNotifications: () => Promise<void>;
  /** 移除已显示的所有通知 */
  dismissAllNotifications: () => Promise<void>;
  /** 最后一次点击的通知 */
  lastNotificationResponse: Notifications.NotificationResponse | null;
  /** 错误信息 */
  error: string | null;
}

// ------------------------------------------------------------------
// 常量
// ------------------------------------------------------------------

/** Android 通知通道 ID */
const ANDROID_CHANNEL_ID = 'ailife-default';

/** Android 通知通道名称 */
const ANDROID_CHANNEL_NAME = 'AILife 默认通知';

// ------------------------------------------------------------------
// Hook
// ------------------------------------------------------------------

/**
 * @returns 通知相关的状态和操作函数。
 */
export function useNotifications(): UseNotificationsReturn {
  // ================================================================
  //  状态
  // ================================================================

  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [permissionStatus, setPermissionStatus] =
    useState<Notifications.NotificationPermissionsStatus | null>(null);
  const [isRequesting, setIsRequesting] = useState(false);
  const [lastNotificationResponse, setLastNotificationResponse] =
    useState<Notifications.NotificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ================================================================
  //  Refs
  // ================================================================

  /** 组件是否已卸载 */
  const isUnmountedRef = useRef(false);

  /** 通知接收监听器引用 */
  const receivedListenerRef =
    useRef<Notifications.Subscription | null>(null);

  /** 通知响应（点击）监听器引用 */
  const responseListenerRef =
    useRef<Notifications.Subscription | null>(null);

  useEffect(() => {
    isUnmountedRef.current = false;
    return () => {
      isUnmountedRef.current = true;
    };
  }, []);

  // ================================================================
  //  初始化：设置 Android 通知通道 & 获取现有权限 & 监听
  // ================================================================

  useEffect(() => {
    /**
     * 设置 Android 通知通道（Android 8.0+ 要求）。
     */
    const setupAndroidChannel = async () => {
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
          name: ANDROID_CHANNEL_NAME,
          importance: Notifications.AndroidImportance.DEFAULT,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#FF6900', // AILife 主题色
        });
      }
    };

    /**
     * 获取当前通知权限状态。
     */
    const checkExistingPermission = async () => {
      const existingStatus = await Notifications.getPermissionsAsync();
      if (!isUnmountedRef.current) {
        setPermissionStatus(existingStatus);
      }

      // 如果已授权，尝试获取推送令牌
      if (existingStatus.status === 'granted') {
        try {
          const token = await Notifications.getExpoPushTokenAsync({
            projectId:
              process.env.EXPO_PUBLIC_EXPO_PROJECT_ID ?? undefined,
          });
          if (!isUnmountedRef.current) {
            setExpoPushToken(token.data);
          }
        } catch (err) {
          console.warn('[useNotifications] getExpoPushTokenAsync failed:', err);
        }
      }
    };

    setupAndroidChannel();
    checkExistingPermission();

    // ---- 监听通知接收 ----
    receivedListenerRef.current =
      Notifications.addNotificationReceivedListener((notification) => {
        if (isUnmountedRef.current) return;
        console.log('[useNotifications] Notification received:', notification);
      });

    // ---- 监听通知点击 ----
    responseListenerRef.current =
      Notifications.addNotificationResponseReceivedListener((response) => {
        if (isUnmountedRef.current) return;
        console.log(
          '[useNotifications] Notification response:',
          response.notification.request.content
        );
        setLastNotificationResponse(response);
      });

    // ---- 清理 ----
    return () => {
      if (receivedListenerRef.current) {
        Notifications.removeNotificationSubscription(
          receivedListenerRef.current
        );
      }
      if (responseListenerRef.current) {
        Notifications.removeNotificationSubscription(
          responseListenerRef.current
        );
      }
    };
  }, []);

  // ================================================================
  //  公开：请求权限
  // ================================================================

  /**
   * 请求通知权限（本地通知 + 远程推送）。
   *
   * @returns `true` 如果用户授予了权限。
   */
  const requestPermission = useCallback(async (): Promise<boolean> => {
    setIsRequesting(true);
    setError(null);

    try {
      const { status, ...rest } =
        await Notifications.requestPermissionsAsync({
          ios: {
            allowAlert: true,
            allowBadge: true,
            allowSound: true,
          },
        });

      const result = { status, ...rest };
      setPermissionStatus(result);

      if (status === 'granted') {
        // 获取推送令牌
        try {
          const token = await Notifications.getExpoPushTokenAsync({
            projectId:
              process.env.EXPO_PUBLIC_EXPO_PROJECT_ID ?? undefined,
          });
          setExpoPushToken(token.data);
        } catch (err) {
          console.warn('[useNotifications] getExpoPushTokenAsync failed:', err);
        }
        return true;
      }

      return false;
    } catch (err: any) {
      console.error('[useNotifications] requestPermission error:', err);
      return false;
    } finally {
      if (!isUnmountedRef.current) {
        setIsRequesting(false);
      }
    }
  }, []);

  // ================================================================
  //  公开：显示通知
  // ================================================================

  /**
   * 显示一条本地通知。
   *
   * @param title - 通知标题。
   * @param body - 通知正文。
   * @param options - 可选配置（副标题、数据载荷、触发方式等）。
   * @returns 通知的唯一标识符（可用于取消）。
   */
  const showNotification = useCallback(
    async (
      title: string,
      body: string,
      options: ShowNotificationOptions = {}
    ): Promise<string | undefined> => {
      const { subtitle, data, sound = true, trigger = null } = options;

      // 如果尚未获得权限，自动请求一次
      if (permissionStatus?.status !== 'granted') {
        const granted = await requestPermission();
        if (!granted) {
          console.warn(
            '[useNotifications] Cannot show notification: permission denied'
          );
          return;
        }
      }

      try {
        const scheduleResult =
          await Notifications.scheduleNotificationAsync({
            content: {
              title,
              body,
              subtitle,
              data,
              sound: sound === true ? undefined : sound || undefined,
            },
            trigger: resolveTrigger(trigger),
          });

        return scheduleResult;
      } catch (err: any) {
        console.error('[useNotifications] showNotification error:', err);
        return;
      }
    },
    [permissionStatus, requestPermission]
  );

  // ================================================================
  //  公开：取消 & 清除通知
  // ================================================================

  /**
   * 取消所有尚未触发的计划通知。
   */
  const cancelAllNotifications = useCallback(async () => {
    try {
      await Notifications.cancelAllScheduledNotificationsAsync();
    } catch (err) {
      console.error('[useNotifications] cancelAllNotifications error:', err);
    }
  }, []);

  /**
   * 移除所有已显示在通知栏中的通知。
   */
  const dismissAllNotifications = useCallback(async () => {
    try {
      await Notifications.dismissAllNotificationsAsync();
    } catch (err) {
      console.error('[useNotifications] dismissAllNotifications error:', err);
    }
  }, []);

  // ================================================================
  //  内部辅助：解析 trigger 参数
  // ================================================================

  /**
   * 将用户友好的 trigger 参数转换为 Expo Notifications 接受的格式。
   */
  function resolveTrigger(
    trigger: ShowNotificationOptions['trigger']
  ): Notifications.NotificationTriggerInput | null {
    if (trigger === null) return null;

    if (trigger instanceof Date) {
      const seconds = Math.floor((trigger.getTime() - Date.now()) / 1000);
      return seconds > 0 ? { seconds } : null;
    }

    if (typeof trigger === 'object' && 'seconds' in trigger) {
      return { seconds: trigger.seconds };
    }

    return null;
  }

  // ================================================================
  //  返回
  // ================================================================

  return {
    expoPushToken,
    permissionStatus,
    isRequesting,
    showNotification,
    requestPermission,
    cancelAllNotifications,
    dismissAllNotifications,
    lastNotificationResponse,
    error,
  };
}
