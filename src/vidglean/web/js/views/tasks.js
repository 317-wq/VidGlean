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

// 阶段简称固定下来：Markdown 生成简称 MD，不要用前两个字截断
const STAGE_NAME = {
  link_parse: '链接',
  subtitle: '字幕',
  ai_analyze: 'AI',
  render_md: 'MD',
};

function stagePill(stage) {
  const label = STAGE_NAME[stage.stage] || stage.label || stage.stage;
  const text = STAGE_SHORT[stage.status] || stage.status;
  return el(
    'span',
    { class: `stage-pill ${stage.status}`, title: `${stage.label || stage.stage}：${text}` },
    label,
  );
}

function stageBar(stages) {
  if (!stages || !stages.length) return el('span', { class: 'muted small' }, '-');
  return el('div', { class: 'stage-bar' }, ...stages.map(stagePill));
}

let showDone = localStorage.getItem('vg-show-done') === '1';

export async function renderTasks(root, state) {
  root.innerHTML = '';

  const toggle = el('input', {
    type: 'checkbox',
    checked: showDone,
    onchange: (event) => {
      showDone = event.target.checked;
      localStorage.setItem('vg-show-done', showDone ? '1' : '0');
      renderTasks(root, state);
    },
  });

  root.append(
    el(
      'div',
      { class: 'page-head' },
      el('h1', {}, '任务'),
      el('span', { class: 'muted small' }, '只显示还没结束的任务；完成后会从列表消失，文档在「全部文档」里'),
      el('div', { class: 'spacer' }),
      el('label', { class: 'row small muted' }, toggle, '显示已完成'),
      el(
        'button',
        {
          class: 'btn small',
          onclick: async () => {
            if (!window.confirm('清空已完成和已取消的任务记录？文档不受影响。')) return;
            try {
              const result = await api.post('/api/tasks/cleanup', {});
              toast(`已清理 ${result.removed} 条记录`);
              renderTasks(root, state);
            } catch (error) {
              if (error.code === 'HTTP_405') {
                toast('服务端还是旧版本，请重启 vidglean 后再试', 'error');
              } else {
                errorToast(error);
              }
            }
          },
        },
        '清理已完成',
      ),
      el('button', { class: 'btn small', onclick: () => renderTasks(root, state) }, '刷新'),
    ),
  );

  let data;
  try {
    data = await api.get(`/api/tasks?limit=100&include_done=${showDone ? 'true' : 'false'}`);
  } catch (error) {
    root.append(el('div', { class: 'empty' }, error.message));
    return;
  }
  // 服务端已过滤；这里再挡一层，避免旧进程把已完成的任务又带出来
  data.items = showDone
    ? data.items
    : data.items.filter((task) => task.status !== 'succeeded' && task.status !== 'canceled');
  if (!data.items.length) {
    root.append(
      emptyState(showDone ? '还没有任务记录，先去导入一个视频吧' : '没有进行中的任务'),
    );
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
        { class: 'task-name' },
        task.document_id
          ? el(
              'a',
              { href: `#/doc/${task.document_id}`, title: task.document_title || task.source_url },
              task.document_title || task.source_url,
            )
          : el('span', { title: task.source_url }, task.source_url),
        task.error_message ? el('div', { class: 'muted small' }, task.error_message) : null,
      ),
      el('td', { class: 'nowrap' }, statusBadge(task.status)),
      el('td', {}, stageBar(details[index])),
      el('td', { class: 'nowrap' }, `${task.retry_count || 0}`),
      el('td', { class: 'muted small nowrap' }, fmtDate(task.updated_at)),
      el(
        'td',
        {},
        el(
          'div',
          { class: 'row nowrap' },
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
            : null,
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
