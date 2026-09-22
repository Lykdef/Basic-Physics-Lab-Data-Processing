const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('labDesktop', { calculate: payload => ipcRenderer.invoke('calculate',payload), openProject: () => ipcRenderer.invoke('project:open'), saveProject: (name, content) => ipcRenderer.invoke('project:save', name, content) });
