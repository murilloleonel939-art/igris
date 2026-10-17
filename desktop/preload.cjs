const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('igrisDesktop', {
  platform: process.platform,
  isDesktop: true
})
