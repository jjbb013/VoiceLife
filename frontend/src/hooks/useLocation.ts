/**
 * useLocation — 位置获取 Hook
 *
 * 封装 Expo Location 的位置获取功能：
 * - 请求前台位置权限
 * - 获取当前设备坐标
 * - 支持通过反向地理编码获取位置名称
 * - 提供手动刷新方法
 *
 * @example
 * ```tsx
 * const { location, error, getCurrentLocation } = useLocation();
 *
 * useEffect(() => {
 *   getCurrentLocation();
 * }, [getCurrentLocation]);
 *
 * if (location) {
 *   console.log(location.latitude, location.longitude, location.name);
 * }
 * ```
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import * as Location from 'expo-location';

// ------------------------------------------------------------------
// 类型定义
// ------------------------------------------------------------------

/** 位置数据结构 */
export interface LocationData {
  /** 纬度 */
  latitude: number;
  /** 经度 */
  longitude: number;
  /** 位置名称（如通过反向地理编码获取） */
  name?: string;
  /** 精度（米） */
  accuracy?: number | null;
  /** 获取时间戳 */
  timestamp?: number;
}

/** useLocation 返回的 API */
export interface UseLocationReturn {
  /** 当前位置数据，未获取时为 null */
  location: LocationData | null;
  /** 是否有正在进行的定位请求 */
  isLoading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 手动触发位置获取 */
  getCurrentLocation: () => Promise<void>;
  /** 清除当前位置 */
  clearLocation: () => void;
}

// ------------------------------------------------------------------
// 常量
// ------------------------------------------------------------------

/** 位置获取超时时间（毫秒） */
const LOCATION_TIMEOUT_MS = 15000;

/** 期望的位置精度 */
const LOCATION_ACCURACY = Location.Accuracy.Balanced;

// ------------------------------------------------------------------
// Hook
// ------------------------------------------------------------------

/**
 * @returns 位置状态和控制方法。
 */
export function useLocation(): UseLocationReturn {
  // ================================================================
  //  状态
  // ================================================================

  const [location, setLocation] = useState<LocationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ================================================================
  //  Refs
  // ================================================================

  /** 标记组件是否已卸载 */
  const isUnmountedRef = useRef(false);

  /** 是否有正在进行的定位请求（用于防重复提交） */
  const isFetchingRef = useRef(false);

  useEffect(() => {
    isUnmountedRef.current = false;
    return () => {
      isUnmountedRef.current = true;
    };
  }, []);

  // ================================================================
  //  核心方法：获取当前位置
  // ================================================================

  /**
   * 获取当前设备位置。
   *
   * 流程：
   * 1. 请求前台位置权限。
   * 2. 调用 `getCurrentPositionAsync` 获取坐标。
   * 3. （可选）通过反向地理编码获取位置名称。
   * 4. 更新 location 状态。
   *
   * 该方法具有防重复提交机制，如果前一次定位尚未完成，
   * 新的调用会被忽略。
   */
  const getCurrentLocation = useCallback(async () => {
    // 防重复提交
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    setIsLoading(true);
    setError(null);

    try {
      // ---- 1. 请求权限 ----
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setError('位置权限被拒绝，请在系统设置中开启');
        setIsLoading(false);
        isFetchingRef.current = false;
        return;
      }

      // ---- 2. 获取坐标 ----
      const position = await Location.getCurrentPositionAsync({
        accuracy: LOCATION_ACCURACY,
      });

      if (isUnmountedRef.current) {
        isFetchingRef.current = false;
        return;
      }

      const { latitude, longitude, accuracy } = position.coords;

      const locationData: LocationData = {
        latitude,
        longitude,
        accuracy,
        timestamp: position.timestamp,
      };

      // ---- 3. 反向地理编码（获取位置名称） ----
      try {
        const addresses = await Location.reverseGeocodeAsync({
          latitude,
          longitude,
        });
        if (addresses.length > 0) {
          const addr = addresses[0];
          // 拼接有意义的地址字段
          const parts = [
            addr.name,
            addr.street,
            addr.city,
            addr.region,
            addr.country,
          ].filter(Boolean);
          locationData.name = parts.slice(0, 3).join(', ');
        }
      } catch (geoErr) {
        // 反向地理编码失败不应阻塞主流程
        console.warn('[useLocation] reverseGeocode failed:', geoErr);
      }

      if (isUnmountedRef.current) {
        isFetchingRef.current = false;
        return;
      }

      setLocation(locationData);
    } catch (err: any) {
      if (isUnmountedRef.current) {
        isFetchingRef.current = false;
        return;
      }

      console.error('[useLocation] getCurrentLocation error:', err);

      // 区分不同类型的错误
      if (err?.message?.includes('timeout')) {
        setError('定位超时，请检查 GPS 信号');
      } else {
        setError(err?.message ?? '获取位置失败');
      }
    } finally {
      if (!isUnmountedRef.current) {
        setIsLoading(false);
      }
      isFetchingRef.current = false;
    }
  }, []);

  // ================================================================
  //  辅助方法：清除位置
  // ================================================================

  const clearLocation = useCallback(() => {
    setLocation(null);
    setError(null);
  }, []);

  // ================================================================
  //  返回
  // ================================================================

  return {
    location,
    isLoading,
    error,
    getCurrentLocation,
    clearLocation,
  };
}
