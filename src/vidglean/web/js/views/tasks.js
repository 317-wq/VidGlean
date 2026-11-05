import { api } from '../api.js';
import { el, emptyState, errorToast, fmtDate, statusBadge, STATUS_TEXT, toast } from '../ui.js';

const ACTIONS = {
  pending: ['cancel'],
  running: ['pause', 'cancel'],
  paused: ['resume', 'cancel'],
  failed: ['retry', 'cancel'],
  interrupted: ['retry'],
  succeeded: [],
  canceled: [],
};

const ACTION_TEXT = {
  retry: '重试',
  pause: '暂停',
  resume: '继续',
  cancel: '取消',
};

const STAGE_SHORT = {
  pending: '等待',
  running: '进行',
  succeeded: '完成',
  failed: '失败',
  skipped: '跳过',
};

function stagePill(stage) {
  const label = stage.label || stage.stage;
  const text = STAGE_SHORT[stage.status] || stage.status;
  return el('span', { class: `stage-pill ${stage.status}`, title: `${label}：${text}` }, label.slice(0, 2));
}

function stageBar(stages) {
  if (!stages || !stages.length) return el('span', { class: 'muted small' }, '-');
  return el('div', { class: 'stage-bar' }, ...stages.map(stagePill));
}

export async function renderTasks(root, state) {
  root.innerHTML = '';
  root.append(
    el(
      'div',
      { class: 'page-head' },
      el('h1', {}, '任务'),
      el('span', { class: 'muted small' }, '任务中断后不会自动恢复，需要手动重试'),
      el('div', { class: 'spacer' }),
      el('button', { class: 'btn small', onclick: () => renderTasks(root, state) }, '刷新'),
    ),
  );

  let data;
  try {
    data = await api.get('/api/tasks?limit=100');
  } catch (error) {
    root.append(el('div', { class: 'empty' }, error.message));
    return;
  }
  if (!data.items.length) {
    root.append(emptyState('还没有任务，先去导入一个视频吧'));
    return;
  }

  const details = await Promise.all(
    data.items.map(async (task) => {
      try {
        return (await api.get(`/api/tasks/${task.id}`)).stages;
      } catch (error) {
        return [];
      }
    }),
  );

  const rows = data.items.map((task, index) =>
    el(
      'tr',
      {},
      el(
        'td',
        {},
        task.document_id
          ? el('a', { href: `#/doc/${task.document_id}` }, task.document_title || task.source_url)
          : el('span', {}, task.source_url),
        task.error_message ? el('div', { class: 'muted small' }, task.error_message) : null,
      ),
      el('td', {}, statusBadge(task.status)),
      el('td', {}, stageBar(details[index])),
      el('td', {}, `${task.retry_count || 0}`),
      el('td', { class: 'muted small' }, fmtDate(task.updated_at)),
      el(
        'td',
        {},
        el(
          'div',
          { class: 'row' },
          ...(ACTIONS[task.status] || []).map((action) =>
            el(
              'button',
              {
                class: 'btn small',
                onclick: async () => {
                  try {
                    await api.post(`/api/tasks/${task.id}/${action}`, {});
                    toast(`已${ACTION_TEXT[action]}`);
                    renderTasks(root, state);
                  } catch (error) {
                    errorToast(error);
                  }
                },
              },
              ACTION_TEXT[action],
            ),
          ),
          task.document_id
            ? el(
                'button',
                { class: 'btn small', onclick: () => (location.hash = `#/doc/${task.document_id}`) },
                '打开文档',
              )
            : el('button', { class: 'btn small', onclick: () => (location.hash = '#/home') }, '去导入'),
        ),
      ),
    ),
  );

  root.append(
    el(
      'table',
      { class: 'task-table' },
      el(
        'thead',
        {},
        el(
          'tr',
          {},
          el('th', {}, '视频'),
          el('th', {}, '状态'),
          el('th', {}, '阶段'),
          el('th', {}, '重试'),
          el('th', {}, '更新时间'),
          el('th', {}, '操作'),
        ),
      ),
      el('tbody', {}, ...rows),
    ),
  );
}
