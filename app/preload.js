// Ponte mínima entre a cena e o app: navegação das telas, endereço atual e volume.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('escritorioApp', {
  isApp: true,
  nav: (name, cmd) => ipcRenderer.invoke('nav', name, cmd),
  volume: (name, v) => ipcRenderer.invoke('volume', name, v),
  onFrameUrl: cb => ipcRenderer.on('frame-url', (e, name, url) => cb(name, url)),
  onEsc: cb => ipcRenderer.on('esc', () => cb()),
});
