import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器：自动附加 user_id
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    try {
      // 从 SecureStore 获取用户 ID（动态导入避免循环依赖）
      const { default: Storage } = await import('./storage');
      const userId = await Storage.getUserId();
      if (userId && config.headers) {
        config.headers['x-user-id'] = userId;
      }
    } catch {
      // 静默失败，不阻塞请求
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// 响应拦截器：统一处理成功和错误
api.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    if (error.response) {
      console.error('API Error:', error.response.status, error.response.data);
    } else if (error.request) {
      console.error('Network Error:', error.message);
    } else {
      console.error('Request Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
