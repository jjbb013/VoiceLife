import React, { useState, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { Switch, Text, Button, Dialog, Portal, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface MeetingToggleProps {
  isMeetingMode: boolean;
  onToggle: (value: boolean) => void;
}

export default function MeetingToggle({ isMeetingMode, onToggle }: MeetingToggleProps) {
  const theme = useTheme();
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingValue, setPendingValue] = useState(false);

  const handleToggle = useCallback(
    (value: boolean) => {
      if (!value && isMeetingMode) {
        // Trying to turn off meeting mode - show confirmation
        setPendingValue(false);
        setShowConfirmDialog(true);
      } else {
        onToggle(value);
      }
    },
    [isMeetingMode, onToggle]
  );

  const confirmTurnOff = useCallback(() => {
    setShowConfirmDialog(false);
    onToggle(false);
  }, [onToggle]);

  const cancelTurnOff = useCallback(() => {
    setShowConfirmDialog(false);
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={styles.iconLabel}>
          <View
            style={[
              styles.iconContainer,
              {
                backgroundColor: isMeetingMode
                  ? theme.colors.primaryContainer
                  : theme.colors.surfaceVariant,
              },
            ]}
          >
            <MaterialCommunityIcons
              name="office-building"
              size={24}
              color={
                isMeetingMode ? theme.colors.primary : theme.colors.onSurfaceVariant
              }
            />
          </View>
          <View style={styles.labelContainer}>
            <Text variant="titleSmall" style={styles.label}>
              会议模式
            </Text>
            <Text
              variant="labelSmall"
              style={{ color: theme.colors.onSurfaceVariant }}
            >
              {isMeetingMode ? '已开启 - 自动区分说话人' : '已关闭'}
            </Text>
          </View>
        </View>

        <Switch
          value={isMeetingMode}
          onValueChange={handleToggle}
          color={theme.colors.primary}
        />
      </View>

      {/* Confirmation Dialog */}
      <Portal>
        <Dialog visible={showConfirmDialog} onDismiss={cancelTurnOff}>
          <Dialog.Icon icon="alert" size={32} color={theme.colors.error} />
          <Dialog.Title style={styles.dialogTitle}>关闭会议模式</Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium">
              关闭会议模式后，系统将不再自动区分不同说话人。当前录音的说话人区分数据将被保留，但新录音将使用普通模式。
            </Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={cancelTurnOff}>取消</Button>
            <Button onPress={confirmTurnOff} textColor={theme.colors.error}>
              确认关闭
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
  },
  iconLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  labelContainer: {
    marginLeft: 12,
  },
  label: {
    fontWeight: '600',
  },
  dialogTitle: {
    textAlign: 'center',
  },
});
