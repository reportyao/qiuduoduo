package com.qiuduoduo.app.jpush;

import android.content.Context;
import android.util.Log;

import cn.jpush.android.api.NotificationMessage;
import cn.jpush.android.service.JPushMessageReceiver;

/**
 * Receives JPush registration / connection / notification callbacks.
 *
 * <p>Notification click currently only logs the extras so we can verify the
 * callback on a real device before wiring deep links into Expo Router.
 */
public class JPushReceiver extends JPushMessageReceiver {
    private static final String TAG = "JPushModule";

    @Override
    public void onRegister(Context context, String registrationId) {
        JPushModule.setRegistrationId(registrationId);
        Log.i(TAG, "registration_id=" + registrationId);
    }

    @Override
    public void onConnected(Context context, boolean connected) {
        Log.i(TAG, "connected=" + connected);
    }

    @Override
    public void onNotifyMessageArrived(Context context, NotificationMessage message) {
        Log.i(TAG, "notification_arrived id=" + message.notificationId);
    }

    @Override
    public void onNotifyMessageOpened(Context context, NotificationMessage message) {
        Log.i(TAG, "notification_opened id=" + message.notificationId
                + " extras=" + message.notificationExtras);
    }
}
