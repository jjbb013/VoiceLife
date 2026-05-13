const { withAndroidManifest } = require('@expo/config-plugins');

module.exports = function withForegroundService(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults;
    const mainApplication = manifest.manifest.application[0];

    mainApplication.service = mainApplication.service || [];
    mainApplication.service.push({
      $: {
        'android:name': 'com.voximplant.foregroundservice.VIForegroundService',
        'android:foregroundServiceType': 'microphone',
        'android:exported': 'false',
      },
    });

    return config;
  });
};
