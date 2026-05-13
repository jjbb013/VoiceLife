import * as SecureStore from 'expo-secure-store';

const Storage = {
  /** 获取存储项 */
  async getItem(key: string): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(key);
    } catch {
      return null;
    }
  },

  /** 设置存储项 */
  async setItem(key: string, value: string): Promise<void> {
    await SecureStore.setItemAsync(key, value);
  },

  /** 删除存储项 */
  async removeItem(key: string): Promise<void> {
    await SecureStore.deleteItemAsync(key);
  },

  // ==========================================
  // 用户相关快捷方法
  // ==========================================

  /** 获取当前用户 ID */
  async getUserId(): Promise<string | null> {
    return this.getItem('user_id');
  },

  /** 设置当前用户 ID */
  async setUserId(userId: string): Promise<void> {
    return this.setItem('user_id', userId);
  },

  /** 清除所有用户数据 */
  async clearUserData(): Promise<void> {
    await this.removeItem('user_id');
  },
};

export default Storage;
