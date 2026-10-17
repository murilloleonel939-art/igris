const { contextBridge } = require('electron')

const { ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('igrisDesktop', {
  platform: process.platform,
  isDesktop: true,
  startVoice: () => ipcRenderer.invoke('voice:start'),
  stopVoice: () => ipcRenderer.invoke('voice:stop'),
  onVoiceEvent: (callback) => ipcRenderer.on('voice:event', (_event, payload) => callback(payload))
})
