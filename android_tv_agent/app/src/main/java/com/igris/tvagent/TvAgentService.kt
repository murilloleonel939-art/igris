package com.igris.tvagent

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Binder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class TvAgentService : Service() {
    private val binder = LocalBinder()
    private val client = OkHttpClient.Builder().pingInterval(30, TimeUnit.SECONDS).build()
    private val handler = Handler(Looper.getMainLooper())
    private var socket: WebSocket? = null
    private lateinit var prefs: SecurePrefs
    private var reconnectAttempts = 0
    private var stopping = false

    private val heartbeat = object : Runnable {
        override fun run() {
            socket?.send(JSONObject().put("type", "heartbeat").toString())
            handler.postDelayed(this, HEARTBEAT_MS)
        }
    }

    inner class LocalBinder : Binder() { fun service(): TvAgentService = this@TvAgentService }

    override fun onCreate() {
        super.onCreate()
        prefs = SecurePrefs(this)
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("Agente TV Box preparado"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (prefs.deviceToken.isNotBlank() || prefs.pairingCode.length >= 6) {
            connect(prefs.websocketUrl, prefs.pairingCode)
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    fun connect(url: String, pairingCode: String) {
        if (!url.startsWith("wss://")) {
            updateNotification("URL WSS inválida")
            return
        }
        prefs.websocketUrl = url
        if (pairingCode.length >= 6) prefs.pairingCode = pairingCode
        stopping = false
        handler.removeCallbacksAndMessages(null)
        socket?.cancel()
        openSocket()
    }

    private fun openSocket() {
        val request = Request.Builder().url(prefs.websocketUrl).build()
        val createdSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val message = if (prefs.deviceToken.isNotBlank()) {
                    JSONObject().put("type", "auth").put("token", prefs.deviceToken)
                } else {
                    JSONObject().put("type", "pair").put("code", prefs.pairingCode).put("device", deviceInfo())
                }
                webSocket.send(message.toString())
                updateNotification("Verificando conexión con Igris")
            }

            override fun onMessage(webSocket: WebSocket, text: String) = handleMessage(text)

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (socket === webSocket) scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket falló: ${t.message}")
                if (socket === webSocket) scheduleReconnect()
            }
        })
        socket = createdSocket
    }

    private fun scheduleReconnect() {
        handler.removeCallbacks(heartbeat)
        if (stopping) return
        val delay = (RECONNECT_BASE_MS * (1L shl reconnectAttempts.coerceAtMost(5))).coerceAtMost(RECONNECT_MAX_MS)
        reconnectAttempts += 1
        updateNotification("TV Box desconectado; reintentando")
        handler.postDelayed({ if (!stopping) openSocket() }, delay)
    }

    private fun authenticated(text: String) {
        reconnectAttempts = 0
        handler.removeCallbacks(heartbeat)
        handler.post(heartbeat)
        updateNotification(text)
    }

    private fun deviceInfo(): JSONObject = JSONObject()
        .put("name", Build.MODEL.ifBlank { "Android TV Box" })
        .put("model", Build.MANUFACTURER + " " + Build.MODEL)
        .put("android_version", Build.VERSION.RELEASE)
        .put("sdk", Build.VERSION.SDK_INT)

    private fun handleMessage(text: String) {
        runCatching {
            val message = JSONObject(text)
            when (message.optString("type")) {
                "paired" -> {
                    prefs.deviceToken = message.optString("token")
                    prefs.pairingCode = ""
                    authenticated("TV Box emparejado")
                }
                "authenticated" -> authenticated("TV Box conectado")
                "command" -> handleAction(message)
                "error" -> updateNotification(message.optString("error", "Error de conexión"))
            }
        }.onFailure { Log.w(TAG, "Mensaje inválido", it) }
    }

    private fun handleAction(message: JSONObject) {
        when (message.optString("action")) {
            "launch_app" -> launchApp(message.optString("package"))
            "key" -> sendKey(message.optString("key"))
            "volume" -> adjustVolume(message.optString("direction"), message.optInt("level", 0))
            "device_info" -> socket?.send(JSONObject().put("type", "device_info").put("device", deviceInfo()).toString())
        }
    }

    private fun launchApp(packageName: String) {
        if (packageName.isBlank()) return
        packageManager.getLaunchIntentForPackage(packageName)?.let {
            it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(it)
        }
    }

    private fun sendKey(key: String) {
        if (!TvAccessibilityService.sendKey(key)) {
            Log.w(TAG, "Habilita Igris TV Agent en Accesibilidad para usar: $key")
        }
    }

    private fun adjustVolume(direction: String, level: Int) {
        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val stream = AudioManager.STREAM_MUSIC
        when (direction) {
            "up" -> audio.adjustStreamVolume(stream, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
            "down" -> audio.adjustStreamVolume(stream, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
            "mute" -> audio.adjustStreamVolume(stream, AudioManager.ADJUST_TOGGLE_MUTE, AudioManager.FLAG_SHOW_UI)
            "set" -> audio.setStreamVolume(stream, level.coerceIn(0, audio.getStreamMaxVolume(stream)), AudioManager.FLAG_SHOW_UI)
        }
    }

    override fun onDestroy() {
        stopping = true
        handler.removeCallbacksAndMessages(null)
        socket?.close(1000, "service stopped")
        client.dispatcher.executorService.shutdown()
        super.onDestroy()
    }

    private fun createNotificationChannel() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "TV Agent", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text: String): Notification = Notification.Builder(this, CHANNEL_ID)
        .setContentTitle("Igris TV Agent").setContentText(text)
        .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth).build()

    companion object {
        private const val TAG = "TvAgentService"
        private const val CHANNEL_ID = "tv_agent"
        private const val NOTIFICATION_ID = 1001
        private const val HEARTBEAT_MS = 30_000L
        private const val RECONNECT_BASE_MS = 2_000L
        private const val RECONNECT_MAX_MS = 60_000L
    }
}
