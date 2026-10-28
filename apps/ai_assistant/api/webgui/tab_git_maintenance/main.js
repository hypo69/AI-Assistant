/**
 * =============================================================================
 * Process Name: AI Assistant WebGUI - Git Maintenance Tab Controller
 * =============================================================================
 * Description:
 *   Клиентский контроллер вкладки tab_git_maintenance.
 *   Управляет загрузкой диагностических срезов, отображением активного репозитория,
 *   отрисовкой светофора состояния, вызовом штатного git gc --auto и проверкой
 *   целостности git fsck.
 *
 * File: main.js
 * Package: apps/ai_assistant/api/webgui/tab_git_maintenance
 * Author: hypo69
 * Copyright: © 2026 hypo69
 * Updated: 2026-10-25 19:25:00
 * =============================================================================
 */

let isOperating = false;
let currentTargetRepoPath = '';

/**
 * Логирует сообщение в блок терминального вывода вкладки.
 */
function logToConsole(message) {
  const consoleEl = document.getElementById('git-maint-tab-console');
  if (!consoleEl) return;
  const time = new Date().toLocaleTimeString('ru-RU');
  consoleEl.textContent = `[${time}] ${message}\n${consoleEl.textContent}`;
}

/**
 * Загружает и отображает текущую диагностику репозитория.
 * @param {string|null} customPath
 */
export async function loadDiagnosis(customPath = null) {
  const btnDiagnose = document.getElementById('btn-git-diagnose');
  if (btnDiagnose) {
    btnDiagnose.disabled = true;
    btnDiagnose.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Оценка...';
  }

  const queryPath = customPath !== null ? customPath : currentTargetRepoPath;
  const url = queryPath
    ? `/api/v1/git/maintenance/diagnosis?repo_path=${encodeURIComponent(queryPath)}`
    : '/api/v1/git/maintenance/diagnosis';

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    currentTargetRepoPath = data.repo_path || '';
    renderActiveRepoInfo(data);
    renderDiagnosis(data);
    renderRepoSelector(data.available_repos || [], currentTargetRepoPath);
    await loadHistory();

    logToConsole(`Диагностика [${data.repo_name}]: ${data.verdict_title}. ${data.recommendation}`);
  } catch (err) {
    console.error('[TabGitMaintenance] Ошибка загрузки диагностики:', err);
    logToConsole(`Ошибка выполнения диагностики: ${err.message}`);
  } finally {
    if (btnDiagnose) {
      btnDiagnose.disabled = false;
      btnDiagnose.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Запустить диагностику';
    }
  }
}

/**
 * Отрисовывает блок сведений об активном репозитории.
 */
function renderActiveRepoInfo(data) {
  const nameEl = document.getElementById('git-active-repo-name');
  const branchTextEl = document.getElementById('git-active-repo-branch-text');
  const commitEl = document.getElementById('git-active-repo-commit');
  const pathEl = document.getElementById('git-active-repo-path');
  const lastCommitEl = document.getElementById('git-active-repo-last-commit');
  const cleanBadge = document.getElementById('git-active-repo-clean');

  const m = data.metrics || {};

  if (nameEl) nameEl.textContent = data.repo_name || m.repo_name || 'Не определён';
  if (branchTextEl) branchTextEl.textContent = data.current_branch || m.current_branch || 'master';
  if (commitEl) commitEl.textContent = `HEAD: ${data.current_commit || m.current_commit || '—'}`;
  if (pathEl) pathEl.textContent = data.repo_path || m.repo_path || '—';

  if (lastCommitEl) {
    lastCommitEl.textContent = m.commit_message ? `• Последний коммит: ${m.commit_message}` : '';
  }

  if (cleanBadge) {
    if (m.is_clean) {
      cleanBadge.className = 'badge bg-success-subtle text-success border border-success-subtle';
      cleanBadge.innerHTML = '<i class="bi bi-check2 me-0.5"></i>Clean';
    } else {
      cleanBadge.className = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle';
      cleanBadge.innerHTML = '<i class="bi bi-pencil-fill me-0.5"></i>Modified';
    }
  }

  // Обновляем бейдж на верхней панели навигации всего приложения
  const topBadge = document.getElementById('head-commit-badge');
  if (topBadge) {
    topBadge.style.cursor = 'pointer';
    topBadge.title = `Активный репозиторий: ${data.repo_name} (${data.current_branch}). Кликните для открытия диагностики`;
    topBadge.innerHTML = `
      <i class="bi bi-git"></i>
      <span>${data.repo_name}: ${data.current_branch} (${data.current_commit})</span>
    `;
    topBadge.onclick = () => {
      if (typeof window.switchTab === 'function') {
        window.switchTab('tab-git-maintenance');
      }
    };
  }
}

/**
 * Наполняет выпадающий список выбора репозитория.
 */
function renderRepoSelector(repos, activePath) {
  const select = document.getElementById('select-git-repo');
  if (!select) return;

  // Исключаем любые проекты кроме рабочих пространств из data (ws-*)
  const wsRepos = (repos || []).filter((r) => r.id && r.id.startsWith('ws-'));

  if (wsRepos.length === 0) {
    select.innerHTML = '<option value="">Нет доступных рабочих пространств</option>';
    return;
  }

  const normActive = (activePath || '').replace(/\\/g, '/').toLowerCase();
  select.innerHTML = wsRepos
    .map((r) => {
      const normR = (r.path || '').replace(/\\/g, '/').toLowerCase();
      const isSelected = normR === normActive ? 'selected' : '';
      const wsId = r.id && r.id.startsWith('ws-') ? r.id.slice(3) : '';
      return `<option value="${r.path}" data-ws-id="${wsId}" ${isSelected}>${r.name} (${r.branch || 'git'})</option>`;
    })
    .join('');
}

/**
 * Отрисовывает полученный вердикт и измеряемые показатели на странице.
 */
function renderDiagnosis(data) {
  const metrics = data.metrics || {};
  const verdict = data.verdict || 'NORMAL';

  // 1. Отрисовка светофора и карточки вердикта
  const iconContainer = document.getElementById('git-verdict-icon-container');
  const iconEl = document.getElementById('git-verdict-icon');
  const badgeEl = document.getElementById('git-verdict-badge');
  const recEl = document.getElementById('git-recommendation-text');
  const expEl = document.getElementById('git-explanation-text');
  const tsEl = document.getElementById('git-last-measured-ts');

  if (tsEl) {
    tsEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleString('ru-RU') : 'Только что';
  }

  if (recEl) recEl.textContent = `Рекомендация: ${data.recommendation || 'Ничего не делать'}`;
  if (expEl) expEl.textContent = data.explanation || '';

  if (badgeEl && iconContainer && iconEl) {
    if (verdict === 'NORMAL') {
      badgeEl.className = 'badge bg-success-subtle text-success border border-success-subtle px-2.5 py-1 fs-6';
      badgeEl.textContent = '🟢 Норма';
      iconContainer.style.backgroundColor = 'var(--badge-success-bg)';
      iconContainer.style.color = 'var(--ui-success)';
      iconEl.className = 'bi bi-check-circle-fill';
    } else if (verdict === 'OBSERVATION') {
      badgeEl.className = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle px-2.5 py-1 fs-6';
      badgeEl.textContent = '🟡 Наблюдение';
      iconContainer.style.backgroundColor = 'var(--badge-warning-bg)';
      iconContainer.style.color = 'var(--ui-warning)';
      iconEl.className = 'bi bi-exclamation-triangle-fill';
    } else {
      badgeEl.className = 'badge bg-danger-subtle text-danger border border-danger-subtle px-2.5 py-1 fs-6';
      badgeEl.textContent = '🔴 Требуется обслуживание';
      iconContainer.style.backgroundColor = 'var(--badge-danger-bg)';
      iconContainer.style.color = 'var(--ui-danger)';
      iconEl.className = 'bi bi-tools';
    }
  }

  // 2. Отрисовка 6 ключевых показателей
  const looseCountEl = document.getElementById('metric-loose-count');
  if (looseCountEl) looseCountEl.textContent = metrics.loose_count ?? 0;

  const looseSizeEl = document.getElementById('metric-loose-size');
  const looseKibEl = document.getElementById('metric-loose-kib');
  if (looseSizeEl) {
    const mb = ((metrics.loose_size_kib || 0) / 1024).toFixed(2);
    looseSizeEl.textContent = `${mb} MiB`;
  }
  if (looseKibEl) looseKibEl.textContent = `${metrics.loose_size_kib ?? 0} КиБ`;

  const packsCountEl = document.getElementById('metric-packs-count');
  const inPackEl = document.getElementById('metric-in-pack-objects');
  if (packsCountEl) packsCountEl.textContent = metrics.packs_count ?? 0;
  if (inPackEl) inPackEl.textContent = `${metrics.in_pack_count ?? 0} упаковано`;

  const packSizeEl = document.getElementById('metric-pack-size');
  if (packSizeEl) {
    const pmb = ((metrics.pack_size_kib || 0) / 1024).toFixed(2);
    packSizeEl.textContent = `${pmb} MiB`;
  }

  const garbageEl = document.getElementById('metric-garbage');
  const prunePackableEl = document.getElementById('metric-prune-packable');
  if (garbageEl) garbageEl.textContent = metrics.garbage_count ?? 0;
  if (prunePackableEl) prunePackableEl.textContent = `${metrics.prune_packable ?? 0} prune-packable`;

  const fsckStatusEl = document.getElementById('metric-fsck-status');
  const danglingEl = document.getElementById('metric-dangling');
  if (fsckStatusEl) {
    if (metrics.connectivity_ok) {
      fsckStatusEl.className = 'fs-5 my-1 text-success d-flex align-items-center justify-content-center gap-1';
      fsckStatusEl.innerHTML = '<i class="bi bi-shield-check"></i> ОК';
    } else {
      fsckStatusEl.className = 'fs-5 my-1 text-danger d-flex align-items-center justify-content-center gap-1';
      fsckStatusEl.innerHTML = '<i class="bi bi-shield-x"></i> Ошибки';
    }
  }
  if (danglingEl) danglingEl.textContent = `${metrics.dangling_count ?? 0} dangling`;
}

/**
 * Загружает историю диагностических срезов и выводит в таблицу.
 */
export async function loadHistory() {
  const tbody = document.getElementById('git-diagnostics-history-body');
  const countBadge = document.getElementById('history-records-count');
  if (!tbody) return;

  try {
    const res = await fetch('/api/v1/git/maintenance/history?limit=15');
    if (!res.ok) return;
    const records = await res.json();

    if (countBadge) countBadge.textContent = `${records.length} записей`;

    if (!records || records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-muted">Журнал пока пуст. Выполните диагностику.</td></tr>`;
      return;
    }

    tbody.innerHTML = records
      .map((r) => {
        const timeStr = r.timestamp ? new Date(r.timestamp).toLocaleString('ru-RU') : '—';
        const v = r.verdict || 'NORMAL';
        let badgeClass = 'bg-success-subtle text-success border-success-subtle';
        let badgeText = '🟢 Норма';
        if (v === 'OBSERVATION') {
          badgeClass = 'bg-warning-subtle text-warning-emphasis border-warning-subtle';
          badgeText = '🟡 Наблюдение';
        } else if (v === 'MAINTENANCE') {
          badgeClass = 'bg-danger-subtle text-danger border-danger-subtle';
          badgeText = '🔴 Обслуживание';
        }

        const m = r.metrics || {};
        const looseMb = ((m.loose_size_kib || 0) / 1024).toFixed(1);
        const packMb = ((m.pack_size_kib || 0) / 1024).toFixed(1);
        const repoLabel = r.repo_name ? `<span class="badge bg-secondary-subtle text-secondary me-1">${r.repo_name}</span>` : '';

        return `
          <tr>
            <td class="text-nowrap small text-muted">${timeStr}</td>
            <td><span class="badge border ${badgeClass}">${badgeText}</span></td>
            <td><strong>${m.loose_count ?? 0}</strong> <span class="text-muted small">(${looseMb} MiB)</span></td>
            <td><strong>${m.packs_count ?? 0}</strong> пак <span class="text-muted small">(${packMb} MiB)</span></td>
            <td class="small">
              <div>${repoLabel}<strong>${r.recommendation || ''}</strong></div>
              <div class="text-muted">${r.explanation || ''}</div>
            </td>
          </tr>
        `;
      })
      .join('');
  } catch (err) {
    console.warn('[TabGitMaintenance] Ошибка загрузки истории:', err);
  }
}

/**
 * Запускает штатную команду git gc --auto.
 */
async function triggerGcAuto() {
  if (isOperating) return;
  const btn = document.getElementById('btn-git-gc-auto');
  isOperating = true;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Оценка условий Git...';
  }

  logToConsole(`Выполнение штатного git gc --auto для ${currentTargetRepoPath || 'активного репозитория'}...`);

  try {
    const url = currentTargetRepoPath
      ? `/api/v1/git/maintenance/gc-auto?repo_path=${encodeURIComponent(currentTargetRepoPath)}`
      : '/api/v1/git/maintenance/gc-auto';
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка запуска');

    logToConsole(`git gc --auto завершен за ${data.elapsed_sec}с. ${data.output}`);
    if (data.diagnosis) {
      renderDiagnosis(data.diagnosis);
      await loadHistory();
    }
  } catch (err) {
    logToConsole(`Ошибка при выполнении git gc --auto: ${err.message}`);
  } finally {
    isOperating = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-lightning-charge-fill me-1"></i> Выполнить git gc --auto';
    }
  }
}

/**
 * Запускает проверку целостности git fsck.
 */
async function triggerFsck() {
  if (isOperating) return;
  const btn = document.getElementById('btn-git-fsck');
  isOperating = true;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Проверка fsck...';
  }

  logToConsole(`Запуск проверки целостности всех объектов базы Git (git fsck --full)...`);

  try {
    const url = currentTargetRepoPath
      ? `/api/v1/git/maintenance/fsck?repo_path=${encodeURIComponent(currentTargetRepoPath)}`
      : '/api/v1/git/maintenance/fsck';
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка fsck');

    logToConsole(`git fsck завершен за ${data.elapsed_sec}с. Результат: ${data.output.slice(0, 300)}...`);
    await loadDiagnosis();
  } catch (err) {
    logToConsole(`Ошибка fsck: ${err.message}`);
  } finally {
    isOperating = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-shield-check me-1"></i> Проверить целостность (fsck)';
    }
  }
}

/**
 * Инициализация вкладки при открытии.
 */
export function init() {
  document.getElementById('btn-git-diagnose')?.addEventListener('click', () => loadDiagnosis());
  document.getElementById('btn-git-gc-auto')?.addEventListener('click', triggerGcAuto);
  document.getElementById('btn-git-fsck')?.addEventListener('click', triggerFsck);
  document.getElementById('btn-clear-tab-console')?.addEventListener('click', () => {
    const el = document.getElementById('git-maint-tab-console');
    if (el) el.textContent = 'Консоль очищена.';
  });

  // Слушатель единого события context:changed
  document.addEventListener('context:changed', (e) => {
    const pane = document.getElementById('tab-git-maintenance') || document.getElementById('git-maintenance');
    const isActive = pane && (pane.classList.contains('active') || pane.classList.contains('show'));
    const repoPath = e.detail?.repoPath;
    if (repoPath) {
      currentTargetRepoPath = repoPath;
      if (isActive) {
        loadDiagnosis(repoPath);
      }
    }
  });

  document.getElementById('select-git-repo')?.addEventListener('change', (e) => {
    const chosenPath = e.target.value;
    const opt = e.target.selectedOptions ? e.target.selectedOptions[0] : null;
    const wsId = opt ? (opt.getAttribute('data-ws-id') || null) : null;
    logToConsole(`Переключение на репозиторий: ${chosenPath || 'Основной проект'}`);
    if (typeof window.setGlobalActiveRepo === 'function') {
      window.setGlobalActiveRepo(chosenPath, wsId);
    } else {
      loadDiagnosis(chosenPath);
    }
  });

  loadDiagnosis();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
