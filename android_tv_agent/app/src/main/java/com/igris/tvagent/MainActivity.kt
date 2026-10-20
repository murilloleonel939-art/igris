package com.igris.tvagent

import android.content.ComponentName
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.IBinder
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private lateinit var prefs: SecurePrefs
    private var service: TvAgentService? = null
    private var bound = false

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            service = (binder as TvAgentService.LocalBinder).service()
            bound = true
        }
        override fun onServiceDisconnected(name: ComponentName) { service = null; bound = false }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = SecurePrefs(this)

        val url = EditText(this).apply {
            hint = "URL WSS"
            setSingleLine(true)
            setText(prefs.websocketUrl)
            isFocusable = true
        }
        val code = EditText(this).apply {
            hint = "Código de emparejamiento (mín. 6 caracteres)"
            setSingleLine(true)
            setText(prefs.pairingCode)
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        val status = TextView(this).apply { text = "Introduce los datos para conectar" }
        val connect = Button(this).apply {
            text = "Guardar y conectar"
            setOnClickListener {
                val codeValue = code.text.toString().trim()
                val urlValue = url.text.toString().trim()
                if (prefs.deviceToken.isBlank() && codeValue.length < 6) {
                    status.text = "El código debe tener al menos 6 caracteres"
                    code.requestFocus()
                } else if (!urlValue.startsWith("wss://")) {
                    status.text = "La URL debe comenzar por wss://"
                    url.requestFocus()
                } else {
                    prefs.pairingCode = codeValue
                    prefs.websocketUrl = urlValue
                    service?.connect(urlValue, codeValue)
                    status.text = "Conectando…"
                }
            }
        }

        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(64, 48, 64, 48)
            addView(TextView(context).apply { text = "TV Agent"; textSize = 28f })
            addView(url)
            addView(code)
            addView(connect)
            addView(status)
        })

        val intent = Intent(this, TvAgentService::class.java)
        ContextCompat.startForegroundService(this, intent)
        bindService(intent, connection, BIND_AUTO_CREATE)
        if (prefs.deviceToken.isNotBlank() || prefs.pairingCode.length >= 6) {
            status.text = "Reconectando con Igris…"
        }
    }

    override fun onDestroy() {
        if (bound) unbindService(connection)
        super.onDestroy()
    }
}
