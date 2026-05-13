import React, { useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Linking,
  Alert,
} from 'react-native';
import {
  Appbar,
  List,
  TextInput,
  Button,
  Divider,
  Switch,
  Dialog,
  Portal,
  Snackbar,
  Text,
  useTheme,
  Card,
  Chip,
} from 'react-native-paper';
import { StatusBar } from 'expo-status-bar';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { APP_INFO, COLORS } from '../../constants';

interface PermissionState {
  microphone: boolean;
  location: boolean;
  calendar: boolean;
  notifications: boolean;
}

export default function SettingsScreen() {
  const theme = useTheme();

  const [userId, setUserId] = useState('user_' + Date.now());
  const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookType, setWebhookType] = useState<'feishu' | 'dingtalk' | 'custom'>('feishu');
  const [permissions, setPermissions] = useState<PermissionState>({
    microphone: false,
    location: false,
    calendar: false,
    notifications: false,
  });
  const [showWebhookDialog, setShowWebhookDialog] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  const showSnackbar = useCallback((message: string) => {
    setSnackbarMessage(message);
    setSnackbarVisible(true);
  }, []);

  const togglePermission = useCallback((key: keyof PermissionState) => {
    setPermissions((prev) => {
      const updated = { ...prev, [key]: !prev[key] };
      return updated;
    });
    showSnackbar(`${key} 权限已${!permissions[key] ? '开启' : '关闭'}`);
  }, [permissions, showSnackbar]);

  const handleSaveUserId = useCallback(() => {
    showSnackbar('用户ID已保存');
  }, [showSnackbar]);

  const handleSaveApiUrl = useCallback(() => {
    showSnackbar('API 地址已保存');
  }, [showSnackbar]);

  const handleSaveWebhook = useCallback(() => {
    setShowWebhookDialog(false);
    showSnackbar('Webhook 已配置');
  }, [showSnackbar]);

  const handleClearData = useCallback(() => {
    setShowClearDialog(false);
    showSnackbar('所有数据已清除');
  }, [showSnackbar]);

  const handleGenerateUserId = useCallback(() => {
    setUserId(`user_${Date.now()}`);
    showSnackbar('已生成新的用户ID');
  }, [showSnackbar]);

  const openPrivacyPolicy = useCallback(() => {
    Linking.openURL('https://ailife.app/privacy').catch(() => {
      showSnackbar('无法打开隐私政策页面');
    });
  }, [showSnackbar]);

  const permissionIcon = (key: keyof PermissionState) => {
    switch (key) {
      case 'microphone': return 'microphone';
      case 'location': return 'map-marker';
      case 'calendar': return 'calendar';
      case 'notifications': return 'bell';
    }
  };

  const permissionLabel = (key: keyof PermissionState) => {
    switch (key) {
      case 'microphone': return '麦克风';
      case 'location': return '位置信息';
      case 'calendar': return '日历';
      case 'notifications': return '通知';
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />

      <Appbar.Header elevated>
        <Appbar.Content title="设置" titleStyle={styles.headerTitle} />
      </Appbar.Header>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* User ID Section */}
        <List.Section>
          <List.Subheader>用户设置</List.Subheader>
          <Card style={styles.card} mode="outlined">
            <Card.Content>
              <Text
                variant="labelMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginBottom: 8 }}
              >
                用户ID（用于数据隔离）
              </Text>
              <TextInput
                mode="outlined"
                value={userId}
                onChangeText={setUserId}
                style={styles.input}
                dense
                right={
                  <TextInput.Icon
                    icon="refresh"
                    onPress={handleGenerateUserId}
                  />
                }
              />
              <Button
                mode="contained"
                onPress={handleSaveUserId}
                style={styles.saveButton}
                compact
              >
                保存
              </Button>
            </Card.Content>
          </Card>
        </List.Section>

        <Divider />

        {/* API Configuration */}
        <List.Section>
          <List.Subheader>API 配置</List.Subheader>
          <Card style={styles.card} mode="outlined">
            <Card.Content>
              <Text
                variant="labelMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginBottom: 8 }}
              >
                后端 API 地址
              </Text>
              <TextInput
                mode="outlined"
                value={apiUrl}
                onChangeText={setApiUrl}
                placeholder="http://localhost:8000"
                style={styles.input}
                dense
                autoCapitalize="none"
                keyboardType="url"
              />
              <Button
                mode="contained"
                onPress={handleSaveApiUrl}
                style={styles.saveButton}
                compact
              >
                保存
              </Button>
            </Card.Content>
          </Card>
        </List.Section>

        <Divider />

        {/* Permissions */}
        <List.Section>
          <List.Subheader>权限管理</List.Subheader>
          <Card style={styles.card} mode="outlined">
            {(Object.keys(permissions) as Array<keyof PermissionState>).map((key, index, arr) => (
              <View key={key}>
                <List.Item
                  title={permissionLabel(key)}
                  left={(props) => (
                    <List.Icon
                      {...props}
                      icon={permissionIcon(key)}
                      color={permissions[key] ? theme.colors.primary : theme.colors.outline}
                    />
                  )}
                  right={() => (
                    <Switch
                      value={permissions[key]}
                      onValueChange={() => togglePermission(key)}
                      color={theme.colors.primary}
                    />
                  )}
                />
                {index < arr.length - 1 && <Divider style={styles.itemDivider} />}
              </View>
            ))}
          </Card>
        </List.Section>

        <Divider />

        {/* Webhook Configuration */}
        <List.Section>
          <List.Subheader>Webhook 推送</List.Subheader>
          <Card style={styles.card} mode="outlined">
            <Card.Content>
              <Text
                variant="labelMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginBottom: 8 }}
              >
                配置飞书/钉钉机器人，自动推送录音摘要
              </Text>
              <View style={styles.webhookTypeRow}>
                <Chip
                  selected={webhookType === 'feishu'}
                  onPress={() => setWebhookType('feishu')}
                  style={styles.webhookChip}
                  icon="send"
                >
                  飞书
                </Chip>
                <Chip
                  selected={webhookType === 'dingtalk'}
                  onPress={() => setWebhookType('dingtalk')}
                  style={styles.webhookChip}
                  icon="send"
                >
                  钉钉
                </Chip>
                <Chip
                  selected={webhookType === 'custom'}
                  onPress={() => setWebhookType('custom')}
                  style={styles.webhookChip}
                  icon="webhook"
                >
                  自定义
                </Chip>
              </View>
              <TextInput
                mode="outlined"
                value={webhookUrl}
                onChangeText={setWebhookUrl}
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
                style={styles.input}
                dense
                autoCapitalize="none"
                keyboardType="url"
              />
              <Button
                mode="contained"
                onPress={handleSaveWebhook}
                style={styles.saveButton}
                compact
              >
                保存配置
              </Button>
            </Card.Content>
          </Card>
        </List.Section>

        <Divider />

        {/* About */}
        <List.Section>
          <List.Subheader>关于</List.Subheader>
          <Card style={styles.card} mode="outlined">
            <Card.Content style={styles.aboutContent}>
              <MaterialCommunityIcons
                name="record-circle"
                size={48}
                color={theme.colors.primary}
              />
              <Text variant="titleLarge" style={styles.appName}>
                {APP_INFO.NAME}
              </Text>
              <Text variant="bodyMedium" style={{ color: theme.colors.onSurfaceVariant }}>
                {APP_INFO.DESCRIPTION}
              </Text>
              <View style={styles.versionRow}>
                <Text variant="labelMedium" style={{ color: theme.colors.outline }}>
                  版本 {APP_INFO.VERSION} (Build {APP_INFO.BUILD_NUMBER})
                </Text>
              </View>
              <Button
                mode="text"
                onPress={openPrivacyPolicy}
                style={styles.privacyButton}
              >
                隐私政策
              </Button>
            </Card.Content>
          </Card>
        </List.Section>

        <Divider />

        {/* Danger Zone */}
        <List.Section>
          <List.Subheader style={{ color: theme.colors.error }}>危险区域</List.Subheader>
          <Card style={[styles.card, styles.dangerCard]} mode="outlined">
            <Card.Content>
              <Text
                variant="bodyMedium"
                style={{ color: theme.colors.onSurfaceVariant, marginBottom: 12 }}
              >
                清除所有本地数据，包括录音文件、说话人信息和设置。此操作不可撤销。
              </Text>
              <Button
                mode="outlined"
                onPress={() => setShowClearDialog(true)}
                textColor={theme.colors.error}
                style={styles.clearButton}
                icon="delete-alert"
              >
                清除所有数据
              </Button>
            </Card.Content>
          </Card>
        </List.Section>
      </ScrollView>

      {/* Clear Data Confirmation Dialog */}
      <Portal>
        <Dialog visible={showClearDialog} onDismiss={() => setShowClearDialog(false)}>
          <Dialog.Icon icon="alert" size={32} color={theme.colors.error} />
          <Dialog.Title style={styles.dialogTitle}>确认清除数据</Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium">
              此操作将永久删除所有本地数据，包括：
            </Text>
            <Text variant="bodySmall" style={styles.dialogList}>
              {'\n'}• 所有录音文件
              {'\n'}• 说话人信息和声纹
              {'\n'}• 转写文本和摘要
              {'\n'}• 应用设置
            </Text>
            <Text variant="bodyMedium" style={{ color: theme.colors.error, marginTop: 12 }}>
              此操作不可撤销！
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setShowClearDialog(false)}>取消</Button>
            <Button onPress={handleClearData} textColor={theme.colors.error}>
              确认删除
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Snackbar */}
      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  headerTitle: {
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 40,
  },
  card: {
    marginHorizontal: 16,
    borderRadius: 12,
  },
  dangerCard: {
    borderColor: '#B00020',
    borderWidth: 1,
  },
  input: {
    backgroundColor: 'transparent',
  },
  saveButton: {
    marginTop: 8,
    alignSelf: 'flex-end',
  },
  webhookTypeRow: {
    flexDirection: 'row',
    marginBottom: 12,
    gap: 8,
  },
  webhookChip: {
    flex: 1,
  },
  itemDivider: {
    marginHorizontal: 16,
  },
  aboutContent: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  appName: {
    fontWeight: '700',
    marginTop: 8,
    letterSpacing: 1,
  },
  versionRow: {
    marginTop: 8,
  },
  privacyButton: {
    marginTop: 8,
  },
  clearButton: {
    borderColor: '#B00020',
  },
  dialogTitle: {
    textAlign: 'center',
  },
  dialogList: {
    marginTop: 8,
    lineHeight: 20,
    color: '#757575',
  },
});
