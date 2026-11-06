package com.qiuduoduo.app.jpush;

import android.util.Log;

import com.facebook.react.bridge.Promise;
import com.qiuduoduo.app.BuildConfig;
import com.facebook.react.bridge.ReactApplicationContext;
import com.facebook.react.bridge.ReactContextBaseJavaModule;
import com.facebook.react.bridge.ReactMethod;

import cn.jpush.android.api.JPushInterface;

/**
 * Minimal JPush bridge: init the SDK and expose the registration id.
 * The app calls initialize() after onboarding; JPush itself lives in the
 * :pushcore process and keeps the connection alive when the JS runtime sleeps.
 */
public class JPushModule extends ReactContextBaseJavaModule {
    private static final String TAG = "JPushModule";
    private static volatile String sRegistrationId = "";
    private final ReactApplicationContext context;

    public JPushModule(ReactApplicationContext context) {
        super(context);
        this.context = context;
    }

    public static void setRegistrationId(String registrationId) {
        sRegistrationId = registrationId == null ? "" : registrationId;
    }

    @Override
    public String getName() {
        return "JPushModule";
    }

    @ReactMethod
    public void initialize(Promise promise) {
        try {
            JPushInterface.setDebugMode(BuildConfig.DEBUG);
            JPushInterface.init(context);
            Log.i(TAG, "initialized");
            promise.resolve(true);
        } catch (Throwable error) {
            Log.e(TAG, "initialize failed", error);
            promise.reject("jpush_init_failed", error);
        }
    }

    @ReactMethod
    public void getRegistrationId(Promise promise) {
        try {
            String id = JPushInterface.getRegistrationID(context);
            if (id == null || id.isEmpty()) id = sRegistrationId;
            promise.resolve(id == null ? "" : id);
        } catch (Throwable error) {
            promise.reject("jpush_registration_failed", error);
        }
    }

    @ReactMethod
    public void isConnected(Promise promise) {
        try {
            promise.resolve(JPushInterface.getConnectionState(context));
        } catch (Throwable error) {
            promise.resolve(false);
        }
    }
}
