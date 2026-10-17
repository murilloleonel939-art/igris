const { app, BrowserWindow, session, shell, ipcMain } = require('electron')
const path = require('node:path')
const { spawn } = require('node:child_process')

const APP_ORIGIN = 'https://webigris.zottagroup.com'
const CHAT_URL = `${APP_ORIGIN}/u/login?next=%2Fu`
let voiceProcess = null
let mainWindow = null

function installNativeVoiceButton(win) {
  win.webContents.executeJavaScript(`(() => {
    if (window.__igrisNativeVoiceInstalled) return
    window.__igrisNativeVoiceInstalled = true
    const button = document.createElement('button')
    button.textContent = '🎙️ Voz local'
    button.title = 'Captura y transcribe con Whisper local'
    Object.assign(button.style, { position: 'fixed', right: '18px', bottom: '72px', zIndex: '9999', border: '1px solid #64748b', borderRadius: '999px', padding: '10px 16px', color: 'white', background: '#1e293b', cursor: 'pointer', fontSize: '14px' })
    document.body.appendChild(button)
    let active = false
    const setState = (text, color) => { button.textContent = text; button.style.background = color }
    button.onclick = async () => {
      if (active) { active = false; await window.igrisDesktop.stopVoice(); setState('🎙️ Voz local', '#1e293b'); return }
      active = true; setState('🔴 Escuchando…', '#991b1b'); await window.igrisDesktop.startVoice()
    }
    window.__igrisNativeVoiceEvent = async (event) => {
      if (event.type === 'state') setState(event.state === 'transcribing' ? '⏳ Transcribiendo…' : '🔴 Escuchando…', event.state === 'transcribing' ? '#92400e' : '#991b1b')
      if (event.type === 'retry') { setState('🔴 Reintento ' + event.attempt + '/3…', '#7c2d12') }
      if (event.type === 'error') { active = false; setState('⚠️ Reintentar voz', '#7f1d1d'); alert('Voz local: ' + event.message) }
      if (event.type === 'result') {
        active = false; setState('🎙️ Voz local', '#1e293b')
        if (!event.text) return
        const input = document.querySelector('input[placeholder*="Escribe un mensaje a Igris"]')
        if (!input) return
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
        setter.call(input, event.text)
        input.dispatchEvent(new Event('input', { bubbles: true }))
        const mail = Array.from(document.querySelectorAll('button')).find((item) => item.textContent.includes('Enviar'))
        if (mail) mail.click()
      }
    }
    window.igrisDesktop.onVoiceEvent(window.__igrisNativeVoiceEvent)
  })()`).catch(() => {})
}

function voiceCommand() {
  const bundled = path.join(process.resourcesPath, 'voice_worker.exe')
  if (process.platform === 'win32' && require('node:fs').existsSync(bundled)) {
    return { command: bundled, args: [] }
  }
  return { command: process.platform === 'win32' ? 'python' : 'python3', args: [path.join(__dirname, 'voice_worker.py')] }
}

function stopVoice() {
  if (voiceProcess) voiceProcess.kill()
  voiceProcess = null
}

ipcMain.handle('voice:start', (event) => {
  stopVoice()
  const voice = voiceCommand()
  voiceProcess = spawn(voice.command, voice.args, { stdio: ['ignore', 'pipe', 'pipe'] })
  voiceProcess.stdout.on('data', (chunk) => {
    for (const line of chunk.toString().split(/\\r?\\n/).filter(Boolean)) {
      try { event.sender.send('voice:event', JSON.parse(line)) } catch {}
    }
  })
  voiceProcess.stderr.on('data', (chunk) => event.sender.send('voice:event', { type: 'error', message: chunk.toString() }))
  voiceProcess.on('close', () => { voiceProcess = null })
  return true
})

ipcMain.handle('voice:stop', () => { stopVoice(); return true })

function isUserUrl(rawUrl) {
  try {
    const url = new URL(rawUrl)
    return url.origin === APP_ORIGIN && (url.pathname === '/u' || url.pathname.startsWith('/u/'))
  } catch {
    return false
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1240,
    height: 820,
    minWidth: 900,
    minHeight: 650,
    title: 'Igris',
    backgroundColor: '#0f172a',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isUserUrl(url)) win.loadURL(url)
    else if (url.startsWith('https://')) shell.openExternal(url)
    return { action: 'deny' }
  })

  const forceUserArea = (url) => {
    if (!isUserUrl(url)) win.loadURL(`${APP_ORIGIN}/u`)
  }

  win.webContents.on('will-navigate', (event, url) => {
    if (!isUserUrl(url)) {
      event.preventDefault()
      if (url.startsWith('https://')) win.loadURL(`${APP_ORIGIN}/u`)
    }
  })

  // Vue Router cambia de ruta sin navegación HTTP; este evento también cubre
  // el redireccionamiento del login a `/` para usuarios administradores.
  win.webContents.on('did-navigate-in-page', (_event, url) => forceUserArea(url))
  win.webContents.on('did-navigate', (_event, url) => forceUserArea(url))

  win.webContents.on('did-finish-load', () => {
    installNativeVoiceButton(win)
  })

  win.loadURL(CHAT_URL)
  mainWindow = win
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(permission === 'media')
  })
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopVoice()
  if (process.platform !== 'darwin') app.quit()
})
