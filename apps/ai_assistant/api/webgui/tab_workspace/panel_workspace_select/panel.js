/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Workspace Select & Directory Tracking Panel
 * =============================================================================
 * Description:
 *   Панель выбора рабочей области, просмотра содержимого директории Git
 *   и включения файлов/папок в отслеживание с опциями конвертации:
 *   - PDF -> Markdown (локальный pypdf vs модель Gemini)
 *   - Изображения -> OCR (локальный Tesseract vs Gemini Vision)
 *   - Звук -> Транскрибация (внешняя модель Google Gemini API).
 *
 * File: panel.js
 * Package: apps/ai_assistant/api/webgui/tab_workspace/panel_workspace_select
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-28 20:05:00
 * =============================================================================
 */

import { fetchJson } from '../common/ui_utils.js';

function matchWorkspace(list, target) {
  if (!target || !Array.isArray(list) || list.length === 0) return null;
  if (typeof window !== 'undefined' && typeof window.findWorkspaceMatch === 'function') {
    return window.findWorkspaceMatch(list, target);
  }
  let decoded = target;
  try { decoded = decodeURIComponent(target); } catch (_) {}
  const clean = String(decoded).trim().normalize('NFC').toLowerCase();
  return list.find(w => {
    const id = (w.workspace_id || '').normalize('NFC').toLowerCase();
    const name = (w.name || '').normalize('NFC').toLowerCase();
    return id === clean || name === clean ||
           id === clean.replace(/\s+/g, '_') ||
           name === clean.replace(/_/g, ' ') ||
           id.replace(/_/g, ' ') === clean.replace(/_/g, ' ');
  }) || null;
}


let currentWorkspaceId = '';
let isLoadingWorkspaces = false;
let onWorkspaceChangeCallback = null;
let telegramScenarioPollTimer = null;
let lastCompletedScenarioRunId = null;

/**
 * Проверяет, является ли рабочая область пространством «דוד משה».
 * @param {string} wsIdOrName
 * @returns {boolean}
 */
export function isDavidMosheWorkspace(wsIdOrName) {
  if (!wsIdOrName) return false;
  let decoded = wsIdOrName;
  try { decoded = decodeURIComponent(wsIdOrName); } catch (_) {}
  const clean = String(decoded)
    .normalize('NFC')
    .replace(/[\u0591-\u05C7]/g, '')
    .replace(/[\s_\-—–]+/g, ' ')
    .trim()
    .toLowerCase();
  return clean === 'דוד משה' || clean === 'דוד מושה';
}

/**
 * Обновляет видимость кнопки сценария Telegram и опрашивает статус 10-сек спиннера.
 */
export async function pollTelegramScenarioStatus() {
  const tgBtn = document.getElementById('btn-ws-telegram-scenario');
  const banner = document.getElementById('ws-telegram-scenario-banner');
  const countdownEl = document.getElementById('ws-telegram-scenario-countdown');
  const targetPathEl = document.getElementById('ws-telegram-scenario-target-path');

  const isDavidMoshe = isDavidMosheWorkspace(currentWorkspaceId);
  if (tgBtn) {
    tgBtn.classList.toggle('d-none', !isDavidMoshe);
    tgBtn.classList.toggle('d-inline-flex', isDavidMoshe);
  }

  if (!isDavidMoshe) {
    if (banner) {
      banner.classList.add('d-none');
      banner.classList.remove('d-flex');
    }
    return false;
  }

  try {
    const res = await fetchJson('/api/v1/workspaces/telegram-scenario/status');
    const scen = res.scenario || {};
    const status = scen.status || 'idle';

    if (status === 'processing') {
      if (banner) {
        banner.classList.remove('d-none');
        banner.classList.add('d-flex');
      }
      if (countdownEl) {
        const rem = Math.max(1, Math.ceil(Number(scen.remaining_seconds ?? 10)));
        countdownEl.textContent = String(rem);
      }
      if (targetPathEl && scen.target_file_path) {
        targetPathEl.textContent = scen.target_file_path;
      }
      return true;
    } else {
      if (banner) {
        banner.classList.add('d-none');
        banner.classList.remove('d-flex');
      }
      if (status === 'completed' && scen.run_id && scen.run_id !== lastCompletedScenarioRunId) {
        lastCompletedScenarioRunId = scen.run_id;
        await loadWorkspaces(currentWorkspaceId || scen.workspace_id, false);
        await loadDirectoryContents(currentWorkspaceId || scen.workspace_id);
        if (onWorkspaceChangeCallback) {
          await onWorkspaceChangeCallback(currentWorkspaceId || scen.workspace_id);
        }
        document.dispatchEvent(new CustomEvent('workspace:changed', {
          detail: { workspaceId: currentWorkspaceId || scen.workspace_id }
        }));
        const toastMsg = (window.i18n && typeof window.i18n.t === 'function'
          ? window.i18n.t('workspace.telegramScenarioCompletedToast')
          : '') || `Файл "${scen.target_file_path || 'שיחה בין דוד משה לשמוליק.md'}" добавлен в рабочую область דוד משה`;
        if (typeof window.showToast === 'function') {
          window.showToast(toastMsg, 'success');
        }
      }
      return false;
    }
  } catch (_) {
    return false;
  }
}

/**
 * Запускает временный опрос статуса только на время активного выполнения спиннера.
 */
export function startTemporaryScenarioPolling() {
  if (telegramScenarioPollTimer) {
    clearInterval(telegramScenarioPollTimer);
    telegramScenarioPollTimer = null;
  }
  telegramScenarioPollTimer = setInterval(async () => {
    const isProcessing = await pollTelegramScenarioStatus();
    if (!isProcessing) {
      clearInterval(telegramScenarioPollTimer);
      telegramScenarioPollTimer = null;
    }
  }, 1000);
}

/**
 * Запускает специальный сценарий Telegram-бота для рабочего пространства «דוד משה» (10 сек спиннер -> добавление файла).
 * @param {string} [triggerFileName]
 */
export async function triggerDavidMosheTelegramScenario(triggerFileName = 'שיחה בין דוד משה לשמוליק') {
  const banner = document.getElementById('ws-telegram-scenario-banner');
  const countdownEl = document.getElementById('ws-telegram-scenario-countdown');
  if (banner) {
    banner.classList.remove('d-none');
    banner.classList.add('d-flex');
  }
  if (countdownEl) {
    countdownEl.textContent = '10';
  }
  try {
    const res = await fetchJson('/api/v1/workspaces/telegram-scenario/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: currentWorkspaceId || 'דוד_משה',
        trigger_file_name: triggerFileName,
        trigger_source: 'webgui',
      }),
    });
    const scen = res.scenario || {};
    if (scen.run_id) {
      lastCompletedScenarioRunId = null;
    }
    // Запускаем временный опрос только на время выполнения
    startTemporaryScenarioPolling();
    return scen;
  } catch (err) {
    console.error('[WorkspaceSelectPanel] Ошибка запуска сценария Telegram:', err);
    return null;
  }
}
window.triggerDavidMosheTelegramScenario = triggerDavidMosheTelegramScenario;

export function getCurrentWorkspaceId() {
  return currentWorkspaceId;
}

export function setCurrentWorkspaceId(id) {
  currentWorkspaceId = id;
}

export function setOnWorkspaceChange(cb) {
  onWorkspaceChangeCallback = cb;
}

/**
 * Возвращает подходящую иконку Bootstrap Icons для расширения файла.
 * @param {string} ext - Расширение файла (.pdf, .png и т.д.)
 * @param {boolean} isDir - Является ли элемент папкой
 * @returns {string} CSS классы иконки
 */
function getFileIconClass(ext, isDir) {
  if (isDir) return 'bi-folder2 text-warning';
  const e = (ext || '').toLowerCase();
  if (e === '.pdf') return 'bi-filetype-pdf text-danger';
  if (['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'].includes(e)) return 'bi-file-earmark-image text-warning-emphasis';
  if (['.wav', '.mp3', '.ogg', '.m4a', '.flac', '.aac'].includes(e)) return 'bi-file-earmark-music text-success';
  if (['.md', '.txt', '.log'].includes(e)) return 'bi-file-earmark-text text-primary';
  if (['.csv', '.tsv', '.xlsx', '.xls'].includes(e)) return 'bi-file-earmark-spreadsheet text-success';
  if (['.docx', '.doc'].includes(e)) return 'bi-file-earmark-word text-primary';
  if (['.py', '.js', '.json', '.html', '.css', '.yaml', '.yml'].includes(e)) return 'bi-file-earmark-code text-info';
  return 'bi-file-earmark text-secondary';
}

/**
 * Загружает и отображает список файлов и папок рабочей области, отслеживаемых Git.
 * @param {string} [wsId] - Идентификатор рабочей области
 */
export async function loadDirectoryContents(wsId = null) {
  const targetId = wsId || currentWorkspaceId;
  const tbody = document.getElementById('ws-directory-contents-table-body');
  const summaryBadge = document.getElementById('ws-dir-summary-badge');
  if (!tbody) return;

  try {
    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetId)}/directory-contents`);
    const items = res.items || [];
    const totalFiles = res.total_files || 0;
    const totalBytes = res.total_size_bytes || 0;
    const branch = res.branch || 'master';
    const head = res.git_head || 'init';

    let totalFormatted = `${totalBytes} B`;
    if (totalBytes >= 1024 * 1024) {
      totalFormatted = `${(totalBytes / (1024 * 1024)).toFixed(2)} MB`;
    } else if (totalBytes >= 1024) {
      totalFormatted = `${(totalBytes / 1024).toFixed(1)} KB`;
    }

    if (summaryBadge) {
      summaryBadge.textContent = `Файлов: ${totalFiles} | Общий объем: ${totalFormatted} | Ветка: ${branch} | Git HEAD: ${head}`;
    }

    if (items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-center py-4 text-muted font-sans-serif">
            <i class="bi bi-inbox me-1"></i>Каталог пуст. Добавьте файлы или папки через форму ниже для начала отслеживания Git.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map((item) => {
      const icon = getFileIconClass(item.extension, item.is_dir);
      const t = (k, def) => (window.i18n && typeof window.i18n.t === 'function' ? window.i18n.t(k, def) : def);
      let statusBadge = `<span class="badge bg-secondary-subtle text-secondary border">${t('workspace.badgeGitNotTracked', 'Не отслеживается')}</span>`;
      if (item.git_status === 'Игнорируется (.gitignore)') statusBadge = '<span class="badge bg-secondary-subtle text-secondary border"><i class="bi bi-eye-slash me-1"></i>.gitignore</span>';
      if (item.git_status === 'Отслеживается (на диске)') statusBadge = `<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle"><i class="bi bi-pin-angle me-1"></i>${t('workspace.badgeGitTrackedOnDisk', 'На диске (Git)')}</span>`;
      if (item.git_status === 'Изменён (на диске)') statusBadge = `<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle"><i class="bi bi-pencil me-1"></i>${t('workspace.badgeGitModifiedOnDisk', 'Изменён (на диске)')}</span>`;
      if (String(item.git_status || '').startsWith('На другом ПК')) statusBadge = `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-usb-drive me-1"></i>${item.git_status}</span>`;
      if (item.git_status === 'Отслеживается') {
        statusBadge = `<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check2 me-1"></i>${t('workspace.badgeGitTracked', 'Отслеживается')}</span>`;
      } else if (item.git_status === 'Изменён') {
        statusBadge = `<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle"><i class="bi bi-pencil me-1"></i>${t('workspace.badgeGitModified', 'Изменён')}</span>`;
      } else if (item.git_status === 'Добавлен') {
        statusBadge = `<span class="badge bg-info-subtle text-info border border-info-subtle"><i class="bi bi-plus me-1"></i>${t('workspace.badgeGitAdded', 'Добавлен')}</span>`;
      }

      const isDir = Boolean(item.is_dir);
      const rowClass = isDir ? 'dir-row' : 'file-row cursor-pointer';
      const tooltip = isDir
        ? (item.rel_path || '')
        : `Нажмите, чтобы открыть в редакторе по умолчанию: ${item.rel_path}`;
      const escapedRelPath = String(item.rel_path || '').replace(/"/g, '&quot;');

      return `
        <tr class="${rowClass}" data-rel-path="${escapedRelPath}" data-is-dir="${isDir}" title="${tooltip}">
          <td>
            <div class="d-flex align-items-center gap-1.5 overflow-hidden text-truncate">
              <i class="bi ${icon}"></i>
              <span class="text-truncate fw-semibold">${item.rel_path}</span>
              ${item.source_mode === 'linked' && (item.qualified_path || item.external_path) ? `<span class="badge bg-secondary-subtle text-secondary border font-monospace ms-1"><i class="bi bi-pc-display me-1"></i>${item.host_name || ''}</span><span class="text-muted font-monospace small text-truncate ms-1" title="${item.qualified_path || item.external_path}">${item.qualified_path || item.external_path}</span>` : ''}
              ${!isDir ? '<i class="bi bi-box-arrow-up-right ms-auto text-secondary opacity-75 small" title="Открыть в редакторе по умолчанию"></i>' : ''}
            </div>
          </td>
          <td class="text-nowrap text-muted">${item.size_formatted}</td>
          <td class="text-nowrap text-secondary">${item.extension}</td>
          <td class="text-nowrap">${statusBadge}</td>
          <td class="text-nowrap text-muted small">${item.modified}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.warn('[WorkspaceSelectPanel] Ошибка загрузки содержимого директории:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-3 text-danger font-sans-serif">
          <i class="bi bi-exclamation-triangle me-1"></i>Ошибка загрузки содержимого папки: ${err.message}
        </td>
      </tr>
    `;
  }
}

/**
 * Проверяет наличие рабочей папки на диске и статус Git через REST API.
 * @param {string} wsId 
 * @param {string} [fallbackPath] 
 */
export async function checkAndDisplayFolderStatus(wsId, fallbackPath = '') {
  const badge = document.getElementById('ws-folder-badge');
  const pathDisplay = document.getElementById('ws-path-display');
  const createBtn = document.getElementById('btn-ws-create-folder');

  if (pathDisplay && fallbackPath) {
    pathDisplay.textContent = fallbackPath;
    pathDisplay.title = fallbackPath;
  }

  try {
    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}/folder-status`);
    const status = res.folder_status || {};

    if (pathDisplay) {
      pathDisplay.textContent = status.path || fallbackPath || '';
      pathDisplay.title = status.path || fallbackPath || '';
    }

    if (badge) {
      if (status.exists && status.has_git) {
        badge.className = 'badge bg-success-subtle text-success border border-success-subtle';
        const headShort = status.git_head ? status.git_head.slice(0, 8) : 'init';
        badge.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>Папка создана (.git: ${headShort})`;
        if (createBtn) createBtn.classList.add('d-none');
      } else if (status.exists && !status.has_git) {
        badge.className = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle';
        badge.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Папка есть, без Git';
        if (createBtn) {
          createBtn.classList.remove('d-none');
          createBtn.innerHTML = '<i class="bi bi-git me-1"></i>Инициализировать Git';
        }
      } else {
        badge.className = 'badge bg-danger-subtle text-danger border border-danger-subtle';
        badge.innerHTML = '<i class="bi bi-x-circle-fill me-1"></i>Папка не найдена на диске';
        if (createBtn) {
          createBtn.classList.remove('d-none');
          createBtn.innerHTML = '<i class="bi bi-folder-plus me-1"></i>Создать рабочую папку';
        }
      }
    }
    return status;
  } catch (err) {
    console.warn('[WorkspaceSelectPanel] Ошибка проверки статуса папки:', err);
    if (badge) {
      badge.className = 'badge bg-secondary-subtle text-secondary border';
      badge.innerHTML = '<i class="bi bi-question-circle me-1"></i>Статус неизвестен';
    }
    return null;
  }
}

export function updateWorkspaceHeader(ws) {
  const gitBadge = document.getElementById('ws-current-git-badge');
  const docsBadge = document.getElementById('ws-docs-count-badge');
  const factsBadge = document.getElementById('ws-facts-count-badge');
  const step2Badge = document.getElementById('ws-step2-active-badge');

  if (!ws) return;
  if (gitBadge) {
    const shortHead = ws.git_head ? ws.git_head.slice(0, 8) : 'init';
    gitBadge.textContent = `Git HEAD: ${shortHead}`;
  }
  if (docsBadge) docsBadge.textContent = `${ws.documents_count || 0} документов`;
  if (factsBadge) factsBadge.textContent = `${ws.active_facts_count || 0} активных фактов`;
  if (step2Badge) step2Badge.textContent = `Область: ${ws.name || ws.workspace_id}`;

  checkAndDisplayFolderStatus(ws.workspace_id, ws.path || '');
  loadObsidianAndEngineStatus(ws.workspace_id);
  pollTelegramScenarioStatus();
}

/**
 * Загружает статус компактного Obsidian Vault и активного движка (Electron / WebView2).
 * @param {string} wsId - Идентификатор рабочей области
 */
export async function loadObsidianAndEngineStatus(wsId = null) {
  const targetId = wsId || currentWorkspaceId;
  const engineBadge = document.getElementById('ws-engine-runtime-badge');
  const obsBadge = document.getElementById('ws-obsidian-status-badge');
  const topicsSpan = document.getElementById('ws-obsidian-topics-list');

  try {
    if (typeof window !== 'undefined' && window.aiEngineBridge && typeof window.aiEngineBridge.getEngineInfo === 'function') {
      const info = await window.aiEngineBridge.getEngineInfo();
      if (engineBadge && info) {
        engineBadge.textContent = `Движок: Electron (${info.electronVersion || 'Chromium + Node.js'})`;
      }
    } else if (engineBadge) {
      const engRes = await fetchJson('/api/v1/engine/status');
      const pref = (engRes.preferred_engine || 'electron').toUpperCase();
      engineBadge.textContent = `Движок: ${pref} (Dual-Engine API)`;
    }
  } catch (_) {}

  try {
    const obsRes = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetId)}/obsidian/status`);
    if (obsBadge) {
      const mdCount = obsRes.markdown_files_count || 0;
      const tCount = obsRes.topics_count || 0;
      obsBadge.textContent = `Obsidian Vault: ${mdCount} .md | Тем: ${tCount}`;
    }
    if (topicsSpan) {
      const topics = obsRes.topics || [];
      topicsSpan.textContent = topics.length > 0 ? `Конспекты (_Topics): ${topics.join(', ')}` : '';
    }
  } catch (err) {
    console.debug('[WorkspaceSelectPanel] Статус Obsidian Vault недоступен:', err);
  }
}

/**
 * Загружает список рабочих пространств и устанавливает активное.
 * @param {string|null} selectId 
 */
export async function loadWorkspaces(selectId = null, triggerCallback = false) {
  if (isLoadingWorkspaces) return;
  isLoadingWorkspaces = true;
  const previousWsId = currentWorkspaceId;
  const selector = document.getElementById('ws-selector');

  if (!selectId && typeof location !== 'undefined') {
    const hashParts = (location.hash || '').replace(/^#/, '').split('#');
    const wsPart = hashParts.find(p => p.startsWith('workspace='));
    if (wsPart) {
      selectId = decodeURIComponent(wsPart.slice('workspace='.length));
    } else if (hashParts[0] === 'tab-workspace' && hashParts[1] && !hashParts[1].startsWith('panel-')) {
      selectId = decodeURIComponent(hashParts[1]);
    }
  }

  if (!selectId) {
    if (typeof window !== 'undefined' && typeof window.getActiveWorkspaceId === 'function') {
      selectId = window.getActiveWorkspaceId();
    }
    if (!selectId) {
      try {
        selectId = localStorage.getItem('ai_assistant_active_workspace') || null;
      } catch (_) {}
    }
  }

  try {
    const data = await fetchJson('/api/v1/workspaces');
    const list = data.workspaces || [];

    if (list.length === 0) {
      currentWorkspaceId = '';
      if (selector) {
        selector.innerHTML = '<option value="">Нет доступных рабочих пространств</option>';
        selector.value = '';
      }
      if (typeof window !== 'undefined' && typeof window.switchTab === 'function') {
        window.switchTab('tab-create-workspace');
      }
      return;
    }

    const matched = selectId ? matchWorkspace(list, selectId) : null;
    if (matched) {
      currentWorkspaceId = matched.workspace_id;
    } else if (list.length > 0) {
      const activeFromList = list.find(w => w.is_active);
      const curMatched = matchWorkspace(list, currentWorkspaceId);
      currentWorkspaceId = curMatched ? curMatched.workspace_id : (activeFromList ? activeFromList.workspace_id : list[0].workspace_id);
    }

    if (selector) {
      selector.innerHTML = list.map(ws => `
        <option value="${ws.workspace_id}" ${ws.workspace_id === currentWorkspaceId ? 'selected' : ''}>
          ${ws.name} [${ws.workspace_id}] — док: ${ws.documents_count || 0}, фактов: ${ws.active_facts_count || 0}
        </option>
      `).join('');
      selector.value = currentWorkspaceId;
    }

    if (typeof window !== 'undefined') {
      if (typeof window.renderDrawerWorkspaces === 'function') {
        window.renderDrawerWorkspaces(list, currentWorkspaceId);
      }
      if (typeof window.highlightActiveDrawerWorkspace === 'function') {
        window.highlightActiveDrawerWorkspace(currentWorkspaceId);
      }
    }

    const activeWs = list.find(w => w.workspace_id === currentWorkspaceId);
    updateWorkspaceHeader(activeWs);
    await loadDirectoryContents(currentWorkspaceId);

    if (triggerCallback && onWorkspaceChangeCallback && previousWsId !== currentWorkspaceId) {
      await onWorkspaceChangeCallback(currentWorkspaceId);
    }
  } catch (err) {
    console.warn('[WorkspaceSelectPanel] Ошибка загрузки рабочих областей:', err);
  } finally {
    isLoadingWorkspaces = false;
  }
}

/**
 * Выбор рабочего пространства из внешних скриптов.
 * @param {string} wsId 
 */
export async function selectWorkspaceInTab(wsId) {
  if (!wsId) return;
  currentWorkspaceId = wsId;
  const selector = document.getElementById('ws-selector');
  if (selector && selector.value !== wsId) {
    selector.value = wsId;
  }
  await loadWorkspaces(wsId, false);
}
window.selectWorkspaceInTab = selectWorkspaceInTab;

const AUDIO_EXTS = ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma'];
const PDF_EXTS = ['.pdf'];
const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.gif'];

function extractFileExtension(filename) {
  if (!filename) return '';
  const idx = filename.lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx).toLowerCase() : '';
}

/**
 * Динамически управляет видимостью блока опций конвертации:
 * блок скрыт по умолчанию; если выбран звуковой файл, PDF или фото —
 * открывается соответствующая секция с возможностью выбора модели или сохранения в сыром виде.
 */
export function updateConvertersVisibility() {
  const convBlock = document.getElementById('ws-converters-block');
  const secPdf = document.getElementById('ws-conv-section-pdf');
  const secOcr = document.getElementById('ws-conv-section-ocr');
  const secAudio = document.getElementById('ws-conv-section-audio');

  if (!convBlock) return;

  const pathInput = document.getElementById('ws-track-input-path');
  const fileUploadInput = document.getElementById('ws-track-upload-input');

  const detectedExts = new Set();

  const rawPath = pathInput?.value?.trim() || '';
  if (rawPath) {
    detectedExts.add(extractFileExtension(rawPath));
  }

  if (fileUploadInput?.files) {
    for (let i = 0; i < fileUploadInput.files.length; i++) {
      detectedExts.add(extractFileExtension(fileUploadInput.files[i].name));
    }
  }

  const hasAudio = [...detectedExts].some(ext => AUDIO_EXTS.includes(ext));
  const hasPdf = [...detectedExts].some(ext => PDF_EXTS.includes(ext));
  const hasImage = [...detectedExts].some(ext => IMAGE_EXTS.includes(ext));

  if (secAudio) secAudio.classList.toggle('d-none', !hasAudio);
  if (secPdf) secPdf.classList.toggle('d-none', !hasPdf);
  if (secOcr) secOcr.classList.toggle('d-none', !hasImage);

  const activeCount = (hasAudio ? 1 : 0) + (hasPdf ? 1 : 0) + (hasImage ? 1 : 0);
  const colClass = activeCount === 1 ? 'col-md-12' : (activeCount === 2 ? 'col-md-6' : 'col-md-4');

  [secAudio, secPdf, secOcr].forEach(sec => {
    if (sec) {
      sec.classList.remove('col-md-12', 'col-md-6', 'col-md-4');
      sec.classList.add(colClass);
    }
  });

  const shouldShow = hasAudio || hasPdf || hasImage;
  convBlock.classList.toggle('d-none', !shouldShow);
}
window.updateConvertersVisibility = updateConvertersVisibility;


/**
 * Открывает файл рабочей области в ассоциированном системном приложении / редакторе по умолчанию.
 * @param {string} relPath - Относительный путь к файлу
 * @param {HTMLElement} [rowElement] - Строка таблицы для визуальной подсветки
 */
export async function openWorkspaceFileInEditor(relPath, rowElement = null) {
  if (!relPath) return;
  const targetWsId = getCurrentWorkspaceId();
  if (rowElement) {
    rowElement.classList.add('table-active');
  }

  try {
    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(targetWsId)}/open-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel_path: relPath }),
    });

    if (res && res.status === 'ok') {
      if (typeof window !== 'undefined' && typeof window.showToast === 'function') {
        window.showToast(`Файл '${relPath}' открыт в редакторе по умолчанию`, 'success');
      }
    }
  } catch (err) {
    console.error(`[WorkspaceSelectPanel] Ошибка открытия файла '${relPath}':`, err);
    if (typeof window !== 'undefined' && typeof window.showToast === 'function') {
      window.showToast(`Ошибка открытия файла: ${err.message}`, 'danger');
    } else {
      alert(`Не удалось открыть файл '${relPath}': ${err.message}`);
    }
  } finally {
    if (rowElement) {
      setTimeout(() => {
        rowElement.classList.remove('table-active');
      }, 400);
    }
  }
}

/**
 * Запрашивает подтверждение и удаляет текущее выбранное рабочее пространство.
 */
export async function deleteCurrentWorkspace() {
  const wsId = currentWorkspaceId;
  if (!wsId) return;

  const confirmPattern = (window.i18n && typeof window.i18n.t === 'function'
    ? window.i18n.t('workspace.deleteWorkspaceConfirm')
    : 'Вы действительно хотите удалить рабочее пространство «{name}»? Все файлы и история Git будут удалены безвозвратно.') || '';
  const confirmMsg = confirmPattern.replace('{name}', wsId);

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(wsId)}`, {
      method: 'DELETE',
    });

    const successPattern = (window.i18n && typeof window.i18n.t === 'function'
      ? window.i18n.t('workspace.deleteWorkspaceSuccess')
      : 'Рабочее пространство «{name}» успешно удалено.') || '';
    const successMsg = successPattern.replace('{name}', wsId);

    if (typeof window.showToast === 'function') {
      window.showToast(successMsg, 'success');
    }

    const nextId = res?.active_workspace_id || '';
    if (nextId) {
      currentWorkspaceId = nextId;
      const targetHash = `#tab-workspace#panel-files#workspace=${encodeURIComponent(nextId)}`;
      try {
        if (typeof location !== 'undefined') {
          location.hash = targetHash;
        }
      } catch (_) {}
    }

    if (typeof window.selectWorkspaceInTab === 'function') {
      await window.selectWorkspaceInTab(nextId, true);
    } else {
      await loadWorkspaces(nextId, true);
    }

    if (typeof window.updateTopWorkspaceDropdown === 'function') {
      window.updateTopWorkspaceDropdown(nextId);
    }
  } catch (err) {
    console.error('[WorkspaceSelectPanel] Ошибка при удалении рабочего пространства:', err);
    const errPattern = (window.i18n && typeof window.i18n.t === 'function'
      ? window.i18n.t('workspace.deleteWorkspaceError')
      : 'Ошибка при удалении пространства: {error}') || '';
    const errMsg = errPattern.replace('{error}', err.message);

    if (typeof window.showToast === 'function') {
      window.showToast(errMsg, 'danger');
    } else {
      alert(errMsg);
    }
  }
}

export function initWorkspaceSelectPanel(onWorkspaceChanged, onAskDemoQuestion) {
  setOnWorkspaceChange(onWorkspaceChanged);

  // Смена активного пространства в селекторе
  document.getElementById('ws-selector')?.addEventListener('change', async (e) => {
    currentWorkspaceId = e.target.value;
    const targetHash = `#tab-workspace#panel-files#workspace=${encodeURIComponent(currentWorkspaceId)}`;
    try {
      if (typeof location !== 'undefined' && location.hash !== targetHash) {
        location.hash = targetHash;
      }
    } catch (_) {}
    if (typeof window.selectWorkspaceInTab === 'function') {
      await window.selectWorkspaceInTab(currentWorkspaceId);
    } else {
      await loadWorkspaces(currentWorkspaceId, false);
    }
    if (typeof window.updateTopWorkspaceDropdown === 'function') {
      window.updateTopWorkspaceDropdown(currentWorkspaceId);
    }
  });

  // Кнопка обновления содержимого папки
  // Делегированный обработчик клика по строке файла для открытия в редакторе по умолчанию
  const dirContentsTableBody = document.getElementById('ws-directory-contents-table-body');
  if (dirContentsTableBody && !dirContentsTableBody.dataset.clickBound) {
    dirContentsTableBody.dataset.clickBound = 'true';
    dirContentsTableBody.addEventListener('click', async (event) => {
      const row = event.target.closest('tr.file-row');
      if (!row) return;

      const isDir = row.getAttribute('data-is-dir') === 'true';
      if (isDir) return;

      const relPath = row.getAttribute('data-rel-path');
      if (!relPath) return;

      await openWorkspaceFileInEditor(relPath, row);
    });
  }

  document.getElementById('btn-refresh-dir-contents')?.addEventListener('click', async () => {
    await loadDirectoryContents(currentWorkspaceId);
    if (typeof window.showToast === 'function') {
      window.showToast('Содержимое папки обновлено', 'info');
    }
  });

  // Кнопка создания/выбора области
  document.getElementById('ws-create-btn')?.addEventListener('click', async () => {
    const idVal = document.getElementById('ws-new-id-input')?.value.trim();
    const pathVal = document.getElementById('ws-new-path-input')?.value.trim();
    if (!idVal) {
      alert('Укажите идентификатор или имя новой рабочей области.');
      return;
    }
    try {
      const res = await fetchJson('/api/v1/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: idVal,
          name: idVal,
          custom_path: pathVal || null,
        }),
      });
      await loadWorkspaces(res.workspace?.workspace_id || idVal);
      if (typeof window.updateTopWorkspaceDropdown === 'function') {
        window.updateTopWorkspaceDropdown(res.workspace?.workspace_id || idVal);
      }
    } catch (err) {
      alert(`Ошибка создания рабочей области: ${err.message}`);
    }
  });

  // Кнопка создания папки на диске при её отсутствии
  document.getElementById('btn-ws-create-folder')?.addEventListener('click', async () => {
    try {
      await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/ensure-folder`, {
        method: 'POST',
      });
      await checkAndDisplayFolderStatus(currentWorkspaceId);
      await loadDirectoryContents(currentWorkspaceId);
      if (typeof window.showToast === 'function') {
        window.showToast('Рабочая папка успешно создана и инициализирован Git', 'success');
      }
    } catch (err) {
      alert(`Ошибка создания рабочей папки: ${err.message}`);
    }
  });

  // Кнопки удаления рабочего пространства
  document.getElementById('ws-btn-delete-workspace')?.addEventListener('click', deleteCurrentWorkspace);
  document.getElementById('btn-ws-delete-folder')?.addEventListener('click', deleteCurrentWorkspace);
  document.getElementById('ws-btn-delete-wizard')?.addEventListener('click', deleteCurrentWorkspace);

  // Кнопка запуска специального сценария Telegram для пространства דוד משה
  document.getElementById('btn-ws-telegram-scenario')?.addEventListener('click', async () => {
    await triggerDavidMosheTelegramScenario('שיחה בין דוד משה לשמוליק');
  });

  // Открытие/закрытие инлайн-панели редактирования пути
  document.getElementById('btn-ws-build-obsidian')?.addEventListener('click', async () => {
    try {
      const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/obsidian/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commit_to_git: true }),
      });
      await loadObsidianAndEngineStatus(currentWorkspaceId);
      await loadDirectoryContents(currentWorkspaceId);
      if (window.showToast) {
        window.showToast(`Obsidian Vault обновлён (документов: ${res.documents_enriched || 0})`, 'success');
      }
    } catch (err) {
      alert(`Ошибка сборки Obsidian Vault: ${err.message}`);
    }
  });

  document.getElementById('btn-ws-open-obsidian')?.addEventListener('click', async () => {
    try {
      const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/obsidian/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine: 'electron' }),
      });
      if (typeof window !== 'undefined' && window.aiEngineBridge && typeof window.aiEngineBridge.openObsidianVault === 'function' && res.vault_path) {
        await window.aiEngineBridge.openObsidianVault(res.vault_path, res.note_name || '_Knowledge_Base.md');
      }
      if (window.showToast) {
        window.showToast(`Открытие хранилища Obsidian (${res.engine || 'electron'})`, 'info');
      }
    } catch (err) {
      alert(`Ошибка открытия в Obsidian: ${err.message}`);
    }
  });

  document.getElementById('btn-ws-compile-topic')?.addEventListener('click', async () => {
    const topicInput = document.getElementById('ws-obsidian-topic-input');
    const queryInput = document.getElementById('ws-obsidian-query-input');
    const topicVal = topicInput?.value?.trim() || '';
    const queryVal = queryInput?.value?.trim() || '';
    if (!topicVal) {
      alert('Укажите название темы для целенаправленной сборки конспекта в Obsidian.');
      return;
    }
    try {
      const res = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/obsidian/topic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topicVal,
          query: queryVal || null,
          commit_to_git: true,
        }),
      });
      if (topicInput) topicInput.value = '';
      if (queryInput) queryInput.value = '';
      await loadObsidianAndEngineStatus(currentWorkspaceId);
      await loadDirectoryContents(currentWorkspaceId);
      if (window.showToast) {
        window.showToast(`Собран конспект _Topics/${res.topic}.md (фактов: ${res.facts_count || 0})`, 'success');
      }
    } catch (err) {
      alert(`Ошибка сборки тематического конспекта: ${err.message}`);
    }
  });


  // Кнопки Обзор файла и Обзор папки для включения в слежение Git
  const trackPathInput = document.getElementById('ws-track-input-path');

  trackPathInput?.addEventListener('input', updateConvertersVisibility);
  trackPathInput?.addEventListener('change', updateConvertersVisibility);
  document.getElementById('ws-track-upload-input')?.addEventListener('change', updateConvertersVisibility);

  document.getElementById('btn-track-browse-file')?.addEventListener('click', async () => {
    try {
      const res = await fetchJson('/api/v1/workspaces/browse-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (res && res.path && trackPathInput) {
        trackPathInput.value = res.path;
        updateConvertersVisibility();
      }
    } catch (err) {
      console.warn('[WorkspaceSelectPanel] Ошибка выбора файла:', err);
    }
  });

  document.getElementById('btn-track-browse-folder')?.addEventListener('click', async () => {
    try {
      const res = await fetchJson('/api/v1/workspaces/browse-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (res && res.path && trackPathInput) {
        trackPathInput.value = res.path;
        updateConvertersVisibility();
      }
    } catch (err) {
      console.warn('[WorkspaceSelectPanel] Ошибка выбора папки:', err);
    }
  });

  // Кнопка добавления в Git-слежение с опциями конвертации
  document.getElementById('btn-track-add-items')?.addEventListener('click', async () => {
    const rawPath = trackPathInput?.value?.trim() || '';
    const fileUploadInput = document.getElementById('ws-track-upload-input');
    const commitMsgInput = document.getElementById('ws-track-commit-msg');
    const statusText = document.getElementById('ws-track-status-text');

    const pdfMode = document.querySelector('input[name="ws-conv-pdf-mode"]:checked')?.value || 'local';
    const ocrMode = document.querySelector('input[name="ws-conv-ocr-mode"]:checked')?.value || 'model';
    const audioMode = document.querySelector('input[name="ws-conv-audio-mode"]:checked')?.value || 'model';
    const commitMsg = commitMsgInput?.value?.trim() || null;

    const hasUploadFiles = fileUploadInput && fileUploadInput.files && fileUploadInput.files.length > 0;

    if (!rawPath && !hasUploadFiles) {
      alert('Укажите путь к файлу/папке на диске или выберите файлы для загрузки.');
      return;
    }

    if (statusText) {
      statusText.innerHTML = '<span class="text-primary"><i class="bi bi-hourglass-split me-1"></i>Обработка и коммит в Git...</span>';
    }

    try {
      let filesCount = 0;

      // 1. Прямая загрузка выбранных файлов
      if (hasUploadFiles) {
        const formData = new FormData();
        for (let i = 0; i < fileUploadInput.files.length; i++) {
          formData.append('files', fileUploadInput.files[i]);
        }
        if (commitMsg) formData.append('commit_message', commitMsg);
        formData.append('pdf_mode', pdfMode);
        formData.append('ocr_mode', ocrMode);
        formData.append('audio_mode', audioMode);

        const resUpload = await fetch(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/files/upload`, {
          method: 'POST',
          body: formData,
        });
        if (!resUpload.ok) {
          throw new Error(`Ошибка загрузки: HTTP ${resUpload.status}`);
        }
        const uploadData = await resUpload.json();
        filesCount += uploadData.files_added || fileUploadInput.files.length;
        fileUploadInput.value = '';
      }

      // 2. Добавление по указанному пути на диске
      if (rawPath) {
        const resItems = await fetchJson(`/api/v1/workspaces/${encodeURIComponent(currentWorkspaceId)}/items`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: [rawPath],
            copy_to_workspace: Boolean(document.getElementById('ws-track-copy-checkbox')?.checked),
            commit_message: commitMsg,
            pdf_mode: pdfMode,
            ocr_mode: ocrMode,
            audio_mode: audioMode,
          }),
        });
        filesCount += resItems.files_added || 1;
        if (trackPathInput) trackPathInput.value = '';
      }

      if (commitMsgInput) commitMsgInput.value = '';
      updateConvertersVisibility();
      await pollTelegramScenarioStatus();
      await loadDirectoryContents(currentWorkspaceId);

      if (statusText) {
        statusText.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Успешно добавлено в Git: ${filesCount} файлов.</span>`;
      }

      if (typeof window.showToast === 'function') {
        window.showToast(`Git начал отслеживание: ${filesCount} файлов зафиксировано`, 'success');
      }
    } catch (err) {
      console.error('[WorkspaceSelectPanel] Ошибка добавления объектов в Git:', err);
      if (statusText) {
        statusText.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>Ошибка: ${err.message}</span>`;
      }
      alert(`Ошибка добавления в Git: ${err.message}`);
    }
  });

  // Перестроение FAISS
  document.getElementById('ws-rebuild-faiss-btn')?.addEventListener('click', async () => {
    try {
      const res = await fetchJson('/api/v1/faiss/rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: currentWorkspaceId }),
      });
      if (window.showToast) {
        window.showToast(`FAISS индекс перестроен (${res.total_vectors} векторов)`, 'success');
      }
    } catch (err) {
      alert(`Ошибка перестроения FAISS: ${err.message}`);
    }
  });
}