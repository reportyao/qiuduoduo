package com.qiuduoduo.app.jpush;

import cn.jpush.android.service.JCommonService;

/**
 * JPush requires the app to declare its own JCommonService subclass. Without it
 * JCore aborts the push process with "missing required service
 * cn.jpush.android.service.JCommonService".
 */
public class JPushCommonService extends JCommonService {}
