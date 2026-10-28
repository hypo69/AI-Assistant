/**
 * =============================================================================
 * Process Name: AI Assistant Electron Shell - Preload Bridge
 * =============================================================================
 * Description:
 *   Безопасный IPC-мост (`contextBridge`) между главным процессом Electron
 *   (Node.js runtime) и общим веб-интерфейсом WebGUI (`window.aiEngineBridge`).
 *   Предоставляет единый контракт Engine Adapter API в браузерном контексте:
 *   - Сканирование и выбор рабочих пространств из директории с Git
 *   - Синхронизация выбора с нативным меню Electron и верхним селектором WebGUI
 *   - Прямой доступ к компактному Obsidian Vault и протоколу obsidian://
 *
 * File: preload.js
 * Package: apps/ai_assistant/electron
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 21:52:00
 * =============================================================================
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aiEngineBridge', {
  engineId: 'electron',
  isElectron: true,
  getInfo: () => ipcRenderer.invoke('engine:get-info'),

  // Работа с рабочими пространствами на основе директории с Git
  listGitWorkspaces: () => ipcRenderer.invoke('workspaces:list-git'),
  setActiveWorkspace: (workspaceId, repoPath) =>
    ipcRenderer.invoke('workspaces:set-active', { workspaceId, repoPath }),
  getActiveWorkspace: () => ipcRenderer.invoke('workspaces:get-active'),
  onWorkspaceSwitched: (callback) => {
    ipcRenderer.on('workspace:switched', (_event, data) => callback(data));
  },
  onWorkspaceListUpdated: (callback) => {
    ipcRenderer.on('workspace:list-updated', (_event) => callback());
  },

  // Работа с Obsidian Vault
  openObsidianVault: (vaultPath, noteName = null) =>
    ipcRenderer.invoke('obsidian:open-vault', { vaultPath, noteName }),
  openVaultFolder: (vaultPath) =>
    ipcRenderer.invoke('obsidian:open-folder', { vaultPath }),
  readMarkdownNote: (filePath) =>
    ipcRenderer.invoke('obsidian:read-note', { filePath }),
  writeMarkdownNote: (filePath, content) =>
    ipcRenderer.invoke('obsidian:write-note', { filePath, content }),
});
