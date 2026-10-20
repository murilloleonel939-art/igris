package com.igris.tvagent

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SecurePrefs(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context,
        "tv_agent_credentials",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    var pairingCode: String
        get() = prefs.getString(KEY_PAIRING_CODE, "") ?: ""
        set(value) { prefs.edit().putString(KEY_PAIRING_CODE, value).apply() }

    var websocketUrl: String
        get() = prefs.getString(KEY_WEBSOCKET_URL, DEFAULT_URL) ?: DEFAULT_URL
        set(value) { prefs.edit().putString(KEY_WEBSOCKET_URL, value).apply() }

    var deviceToken: String
        get() = prefs.getString(KEY_DEVICE_TOKEN, "") ?: ""
        set(value) { prefs.edit().putString(KEY_DEVICE_TOKEN, value).apply() }

    companion object {
        private const val KEY_PAIRING_CODE = "pairing_code"
        private const val KEY_WEBSOCKET_URL = "websocket_url"
        private const val KEY_DEVICE_TOKEN = "device_token"
        const val DEFAULT_URL = "wss://igris.zottagroup.com/api/tvbox/ws"
    }
}
