import { api } from '../api.js';
import { el, emptyState, errorToast, fmtDate, modal, toast } from '../ui.js';

function templateOptions(templates) {
  return templates.map((item) =>
    el('option', { value: item.id }, `${item.name}${item.is_default ? '（默认）' : ''}`),
  );
}

export function openImportPanel() {
  const textarea = el('textarea', {
    class: 'field',
    rows: '4',
    placeholder: '每行一个链接，支持视频页链接、b23.tv 短链或 BV 号',
  });
  const preview = el('div', { class: 'preview-list' });
  const templateSelect = el('select', { class: 'field' }, el('option', { value: '' }, 'AI 自动选择'));
  const depthSelect = el(
    'select',
    { class: 'field' },
    el('option', { value: 'auto' }, '自动'),
    el('option', { value: 'brief' }, '简洁'),
    el('option', { value: 'standard' }, '标准'),
    el('option', { value: 'detailed' }, '详细'),
  );
  const extraInput = el('input', { class: 'field', placeholder: '额外要求，可留空' });
  const parseBtn = el('button', { class: 'btn' }, '解析链接');
  const confirmBtn = el('button', { class: 'btn primary' }, '确认导入');
  confirmBtn.disabled = true;

  let parsed = [];

  const handle = modal({
    title: '导入链接',
    body: el(
      'div',
      {},
      textarea,
      el('div', { class: 'row', style: 'margin-top:10px' }, parseBtn, el('span', { class: 'muted small' }, '最多 20 条')),
      preview,
      el(
        'div',
        { class: 'row', style: 'margin-top:16px' },
        el('div', { style: 'flex:1' }, el('div', { class: 'muted small' }, '模板'), templateSelect),
        el('div', { style: 'width:130px' }, el('div', { class: 'muted small' }, '深度'), depthSelect),
      ),
      el('div', { style: 'margin-top:10px' }, extraInput),
    ),
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      confirmBtn,
    ],
  });

  api
    .get('/api/templates')
    .then((data) => {
      templateSelect.append(...templateOptions(data.items));
    })
    .catch(() => {});

  parseBtn.addEventListener('click', async () => {
    const urls = textarea.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (!urls.length) {
      toast('请先粘贴链接', 'error');
      return;
    }
    parseBtn.disabled = true;
    parseBtn.textContent = '解析中…';
    try {
      const data = await api.post('/api/import/preview', { urls });
      parsed = data.items;
      renderPreview();
    } catch (error) {
      errorToast(error);
    } finally {
      parseBtn.disabled = false;
      parseBtn.textContent = '解析链接';
    }
  });

  function renderPreview() {
    preview.innerHTML = '';
    confirmBtn.disabled = !parsed.some((item) => item.ok);
    parsed.forEach((item, index) => {
      if (!item.ok) {
        preview.append(
          el(
            'div',
            { class: 'preview-item failed' },
            el('div'),
            el(
              'div',
              {},
              el('div', { class: 'title' }, '解析失败'),
              el('div', { class: 'meta' }, item.url),
              el('div', { class: 'meta' }, (item.error && item.error.message) || '未知错误'),
            ),
            el('span', { class: 'badge err' }, '跳过'),
          ),
        );
        return;
      }
      const checked = el('input', { type: 'checkbox', checked: true });
      const duplicate = Boolean(item.exists_document_id);
      const thumb = el('div', { class: 'preview-thumb' });
      if (item.cover_url) {
        const image = el('img', {
          src: `/api/image?url=${encodeURIComponent(item.cover_url)}`,
          alt: '',
          loading: 'lazy',
        });
        // 封面取不到就直接不显示，避免出现裂图
        image.addEventListener('error', () => image.remove());
        thumb.append(image);
      }
      preview.append(
        el(
          'div',
          { class: 'preview-item' },
          thumb,
          el(
            'div',
            {},
            el('div', { class: 'title' }, item.title),
            el('div', { class: 'meta' }, `${item.author} · ${item.duration_text} · ${item.content_type}`),
            duplicate
              ? el('div', { class: 'meta' }, '已有文档，勾选后将重新生成（覆盖正文）')
              : null,
          ),
          el(
            'div',
            { class: 'row' },
            el('span', { class: 'badge' }, duplicate ? '重复' : '新视频'),
            el('label', { class: 'row small' }, checked, '导入'),
          ),
        ),
      );
      item._checkbox = checked;
      item._force = duplicate;
    });
  }

  confirmBtn.addEventListener('click', async () => {
    const items = parsed
      .filter((item) => item.ok && item._checkbox && item._checkbox.checked)
      .map((item) => ({
        url: item.url,
        depth: depthSelect.value,
        template_id: templateSelect.value,
        extra: extraInput.value.trim(),
        force: Boolean(item.exists_document_id),
      }));
    if (!items.length) {
      toast('没有可导入的视频', 'error');
      return;
    }
    confirmBtn.disabled = true;
    try {
      const data = await api.post('/api/import', { items });
      handle.close();
      const okCount = data.tasks.length;
      toast(`已创建 ${okCount} 个任务`);
      if (data.skipped.length) toast(`跳过 ${data.skipped.length} 条`, 'error');
      location.hash = '#/tasks';
    } catch (error) {
      errorToast(error);
    } finally {
      confirmBtn.disabled = false;
    }
  });

  setTimeout(() => textarea.focus(), 40);
}

function docCard(doc, onOpen) {
  return el(
    'article',
    { class: 'card doc-card', onclick: onOpen },
    el('div', { class: 'row' }, el('div', { class: 'title' }, doc.title), el('div', { class: 'spacer' }), doc.starred ? el('span', { class: 'star' }, '★') : null),
    el(
      'div',
      { class: 'meta' },
      el('span', {}, doc.content_type || '其他'),
      el('span', {}, 'Bilibili'),
      el('span', {}, doc.duration ? formatDuration(doc.duration) : ''),
      el('span', {}, fmtDate(doc.created_at)),
    ),
    doc.tags && doc.tags.length
      ? el('div', { class: 'tags' }, ...doc.tags.slice(0, 6).map((tag) => el('span', { class: 'badge' }, tag)))
      : null,
    doc.snippet ? el('div', { class: 'snippet' }, doc.snippet) : null,
  );
}

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export async function renderHome(root, state, view) {
  root.innerHTML = '';
  const starred = view === 'starred' || state.starred;
  const params = new URLSearchParams();
  if (state.q) params.set('q', state.q);
  if (starred) params.set('starred', 'true');
  if (state.category) params.set('category', state.category);

  const setMode = (mode) => {
    state.listMode = mode;
    localStorage.setItem('vg-list-mode', mode);
    renderHome(root, state, view);
  };

  const head = el(
    'div',
    { class: 'page-head' },
    el('h1', {}, starred ? '星标文档' : state.q ? `搜索：${state.q}` : '全部文档'),
    el('span', { class: 'muted small' }, '加载中…'),
    el('div', { class: 'spacer' }),
    el(
      'div',
      { class: 'seg' },
      el(
        'button',
        { class: state.listMode === 'grid' ? 'active' : '', onclick: () => setMode('grid') },
        '卡片',
      ),
      el(
        'button',
        { class: state.listMode === 'list' ? 'active' : '', onclick: () => setMode('list') },
        '列表',
      ),
    ),
  );
  root.append(head);

  // 没配好就跑不起来，直接把缺什么摆在首页
  if (state.health && (!state.health.has_model || !state.health.has_bilibili)) {
    const missing = [];
    if (!state.health.has_model) missing.push('AI 模型');
    if (!state.health.has_bilibili) missing.push('B 站凭证（SESSDATA）');
    root.append(
      el(
        'div',
        { class: 'card import-panel', style: 'border-color:var(--accent)' },
        el(
          'div',
          { class: 'row' },
          el(
            'div',
            {},
            el('div', { style: 'font-weight:600' }, `还差 ${missing.join('、')} 没配置`),
            el(
              'div',
              { class: 'muted small' },
              state.health.has_model
                ? '没有 B 站凭证通常拿不到字幕。'
                : '没有模型无法生成总结；B 站凭证用于获取字幕。',
            ),
          ),
          el('div', { class: 'spacer' }),
          el(
            'button',
            { class: 'btn primary', onclick: () => (location.hash = '#/settings') },
            '去配置',
          ),
        ),
      ),
    );
  }

  if (state.health && state.health.interrupted > 0) {
    root.append(
      el(
        'div',
        { class: 'card import-panel', style: 'border-color:var(--warn)' },
        el(
          'div',
          { class: 'row' },
          el('div', {}, `上次有 ${state.health.interrupted} 个任务没有完成`),
          el('div', { class: 'spacer' }),
          el('button', { class: 'btn small', onclick: () => (location.hash = '#/tasks') }, '去任务页处理'),
        ),
      ),
    );
  }

  const grid = el('div', { class: `doc-grid ${state.listMode === 'list' ? 'list' : ''}` });
  root.append(grid);

  try {
    const data = await api.get(`/api/documents?${params.toString()}`);
    head.querySelector('.muted').textContent = `共 ${data.total} 篇`;
    if (!data.items.length) {
      grid.append(
        emptyState(
          state.q
            ? '没有匹配的文档'
            : '还没有文档，点右上角「导入链接」开始',
        ),
      );
      return;
    }
    for (const doc of data.items) {
      grid.append(docCard(doc, () => (location.hash = `#/doc/${doc.id}`)));
    }
  } catch (error) {
    grid.append(el('div', { class: 'empty' }, error.message));
  }
}
