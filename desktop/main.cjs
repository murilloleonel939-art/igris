const { app, BrowserWindow, session, shell } = require('electron')
const path = require('node:path')

const APP_ORIGIN = 'https://webigris.zottagroup.com'
const CHAT_URL = `${APP_ORIGIN}/u/login?next=%2Fu`

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

  win.webContents.on('will-navigate', (event, url) => {
    if (!isUserUrl(url)) {
      event.preventDefault()
      if (url.startsWith('https://')) shell.openExternal(url)
    }
  })

  win.loadURL(CHAT_URL)
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
  if (process.platform !== 'darwin') app.quit()
})
