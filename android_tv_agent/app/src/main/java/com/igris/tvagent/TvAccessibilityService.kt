package com.igris.tvagent

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent

/** Acciones globales disponibles sin ADB; el usuario debe habilitar este servicio. */
class TvAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        super.onServiceConnected()
        current = this
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    fun performRemoteKey(key: String): Boolean = when (key.uppercase()) {
        "BACK" -> performGlobalAction(GLOBAL_ACTION_BACK)
        "HOME" -> performGlobalAction(GLOBAL_ACTION_HOME)
        "RECENTS" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
        else -> false
    }

    companion object {
        @Volatile private var current: TvAccessibilityService? = null
        fun sendKey(key: String): Boolean = current?.performRemoteKey(key) == true
    }
}
