package com.qiuduoduo.app.jpush;

import android.content.Context;
import android.util.Log;

import cn.jpush.android.service.JPushMessageReceiver;

/** Receives the registration callback from JPush and keeps it available to JS. */
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
}
