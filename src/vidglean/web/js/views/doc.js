import { api, chatStream } from '../api.js';
import {
  debounce,
  el,
  errorToast,
  fmtDate,
  modal,
  renderMath,
  toast,
} from '../ui.js';

function formatDuration(seconds) {
  const total = Number(seconds || 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

async function saveContent(docId, content) {
  await api.put(`/api/documents/${docId}/content`, { content });
}

function editDialog(doc, onSaved) {
  const textarea = el('textarea', { class: 'field code', rows: '22', value: doc.content });
  const status = el('span', { class: 'muted small' }, '自动保存已开启');
  let dirty = false;
  const autosave = debounce(async () => {
    if (!dirty) return;
    dirty = false;
    status.textContent = '保存中…';
    try {
      await api.put(`/api/documents/${doc.id}/content`, { content: textarea.value, snapshot: false });
      status.textContent = '已自动保存';
    } catch (error) {
      status.textContent = '自动保存失败';
    }
  }, 1200);
  textarea.addEventListener('input', () => {
    dirty = true;
    autosave();
  });
  const handle = modal({
    title: '编辑 Markdown 源码',
    width: '900px',
    body: textarea,
    footer: [
      status,
      el('span', { class: 'muted small' }, 'Ctrl+S 保存'),
      el('div', { class: 'spacer' }),
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            try {
              await saveContent(doc.id, textarea.value);
              dirty = false;
              handle.close();
              toast('已保存');
              onSaved();
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '保存',
      ),
    ],
  });
  textarea.addEventListener('keydown', async (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      try {
        await saveContent(doc.id, textarea.value);
        dirty = false;
        handle.close();
        toast('已保存');
        onSaved();
      } catch (error) {
        errorToast(error);
      }
    }
  });
  setTimeout(() => textarea.focus(), 40);
}

function regenerateDialog(doc, templates, onDone) {
  const depth = el(
    'select',
    { class: 'field' },
    el('option', { value: doc.summary_depth || 'standard' }, '保持当前'),
    el('option', { value: 'brief' }, '简洁'),
    el('option', { value: 'standard' }, '标准'),
    el('option', { value: 'detailed' }, '详细'),
  );
  const template = el('select', { class: 'field' }, el('option', { value: '' }, '保持当前'));
  for (const item of templates) {
    template.append(el('option', { value: item.id }, item.name));
  }
  const extra = el('textarea', { class: 'field', rows: '3', placeholder: '例如：重点整理并发编程部分，补充面试考点' });
  const handle = modal({
    title: '重新生成总结',
    width: '560px',
    body: el(
      'div',
      {},
      el('div', { class: 'settings-section', style: 'padding:0;border:0;box-shadow:none' }, el('div', { class: 'muted small' }, '总结深度'), depth),
      el('div', { style: 'margin-top:12px' }, el('div', { class: 'muted small' }, '模板'), template),
      el('div', { style: 'margin-top:12px' }, el('div', { class: 'muted small' }, '额外要求'), extra),
      el('div', { class: 'muted small', style: 'margin-top:10px' }, '重新生成会复用已有字幕，不重复解析链接。'),
    ),
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            try {
              const data = await api.post(`/api/documents/${doc.id}/regenerate`, {
                depth: depth.value || undefined,
                template_id: template.value || undefined,
                extra: extra.value.trim(),
              });
              handle.close();
              toast('已创建重新生成任务');
              onDone(data.task_id);
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '开始生成',
      ),
    ],
  });
}

function assistDialog(doc, onApplied) {
  const instruction = el('textarea', {
    class: 'field',
    rows: '3',
    placeholder: '例如：把「实现步骤」一节改写成更简短的步骤列表，并补充一个代码示例',
  });
  const output = el('div', {});
  const applyBtn = el('button', { class: 'btn primary' }, '应用修改');
  applyBtn.disabled = true;
  let proposed = '';

  const handle = modal({
    title: 'AI 辅助修改',
    width: '880px',
    body: el('div', {}, instruction, el('div', { class: 'row', style: 'margin-top:10px' }, el('button', { class: 'btn', id: 'assist-run' }, '生成修改')), output),
    footer: [el('button', { class: 'btn', onclick: () => handle.close() }, '放弃'), applyBtn],
  });

  handle.dialog.querySelector('#assist-run').addEventListener('click', async () => {
    const text = instruction.value.trim();
    if (!text) {
      toast('请填写修改要求', 'error');
      return;
    }
    output.innerHTML = '';
    output.append(el('div', { class: 'muted small' }, '正在生成…'));
    try {
      const data = await api.post(`/api/documents/${doc.id}/assist`, { instruction: text });
      proposed = data.after;
      output.innerHTML = '';
      output.append(
        el('div', { class: 'muted small', style: 'margin:8px 0' }, '修改预览（红绿为差异）'),
        diffView(data.diff),
        el('details', { style: 'margin-top:10px' }, el('summary', { class: 'small' }, '查看完整修改后内容'), el('pre', { class: 'diff' }, data.after)),
      );
      applyBtn.disabled = false;
    } catch (error) {
      output.innerHTML = '';
      errorToast(error);
    }
  });

  applyBtn.addEventListener('click', async () => {
    try {
      await api.post(`/api/documents/${doc.id}/assist/apply`, { content: proposed });
      handle.close();
      toast('已应用修改');
      onApplied();
    } catch (error) {
      errorToast(error);
    }
  });
}

function diffView(diff) {
  const node = el('pre', { class: 'diff' });
  for (const line of String(diff || '').split('\n')) {
    const cls = line.startsWith('+') && !line.startsWith('+++') ? 'add' : line.startsWith('-') && !line.startsWith('---') ? 'del' : '';
    node.append(el('span', { class: cls }, `${line}\n`));
  }
  return node;
}

function tagDialog(doc, onDone) {
  const input = el('input', { class: 'field', value: (doc.tags || []).join(', '), placeholder: '用逗号分隔，例如：C++, 并发, 面试' });
  const handle = modal({
    title: '编辑标签',
    width: '460px',
    body: input,
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            const tags = input.value
              .split(/[,，]/)
              .map((item) => item.trim())
              .filter(Boolean);
            try {
              await api.patch(`/api/documents/${doc.id}`, { tags });
              handle.close();
              onDone();
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '保存',
      ),
    ],
  });
}

async function categoryDialog(doc, onDone) {
  const data = await api.get('/api/categories');
  const selected = new Set(doc.categories || []);
  const box = el('div', {});
  if (!data.items.length) {
    box.append(el('div', { class: 'muted small' }, '还没有分类，请先在左侧新建'));
  }
  for (const item of data.items) {
    const checkbox = el('input', { type: 'checkbox', checked: selected.has(item.id) });
    checkbox.dataset.id = item.id;
    box.append(el('label', { class: 'row', style: 'padding:6px 0' }, checkbox, item.name));
  }
  const handle = modal({
    title: '归类',
    width: '420px',
    body: box,
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            const ids = [...box.querySelectorAll('input[type=checkbox]')]
              .filter((node) => node.checked)
              .map((node) => node.dataset.id);
            try {
              await api.patch(`/api/documents/${doc.id}`, { categories: ids });
              handle.close();
              onDone();
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '保存',
      ),
    ],
  });
}

function openChat(doc) {
  const drawer = document.getElementById('chat-drawer');
  drawer.hidden = false;
  drawer.innerHTML = '';
  const list = el('div', { class: 'chat-list' });
  const input = el('textarea', { placeholder: '针对这篇文档提问…（Enter 发送，Shift+Enter 换行）' });
  const send = el('button', { class: 'btn primary' }, '发送');

  drawer.append(
    el(
      'header',
      {},
      el('span', {}, '文档对话'),
      el('div', { class: 'spacer' }),
      el(
        'button',
        {
          class: 'btn small',
          onclick: async () => {
            try {
              await api.del(`/api/documents/${doc.id}/messages`);
              list.innerHTML = '';
              toast('对话已清空');
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '清空',
      ),
      el('button', { class: 'btn small', onclick: () => (drawer.hidden = true) }, '关闭'),
    ),
    list,
    el('div', { class: 'chat-input' }, input, send),
  );

  const addBubble = (role, text) => {
    const bubble = el('div', { class: `msg ${role}` }, text);
    list.append(bubble);
    list.scrollTop = list.scrollHeight;
    return bubble;
  };

  for (const message of doc.messages || []) {
    addBubble(message.role, message.content);
  }
  list.scrollTop = list.scrollHeight;

  const submit = async () => {
    const text = input.value.trim();
    if (!text) return;
    addBubble('user', text);
    input.value = '';
    const bubble = addBubble('assistant', '');
    let buffer = '';
    send.disabled = true;
    try {
      await chatStream(doc.id, text, {
        onDelta: (delta) => {
          buffer += delta;
          bubble.textContent = buffer;
          list.scrollTop = list.scrollHeight;
        },
        onDone: () => {
          if (!buffer) bubble.textContent = '（没有返回内容）';
        },
        onError: (payload) => {
          bubble.textContent = `出错了：${payload.message || '未知错误'}`;
        },
      });
    } catch (error) {
      bubble.textContent = `出错了：${error.message}`;
    } finally {
      send.disabled = false;
      input.focus();
    }
  };

  send.addEventListener('click', submit);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      submit();
    }
  });
  setTimeout(() => input.focus(), 60);
}

export async function renderDoc(root, state, docId) {
  root.innerHTML = '';
  let doc;
  try {
    doc = await api.get(`/api/documents/${docId}`);
  } catch (error) {
    root.append(el('div', { class: 'empty' }, error.message));
    return;
  }
  const reload = () => renderDoc(root, state, docId);

  const head = el(
    'div',
    { class: 'doc-head' },
    el(
      'div',
      { style: 'flex:1;min-width:0' },
      el(
        'div',
        { class: 'row small muted', style: 'margin-bottom:6px' },
        el('a', { href: '#/home' }, '← 返回列表'),
        el('span', {}, '·'),
        el('a', { href: doc.source_url, target: '_blank', rel: 'noreferrer' }, '打开原视频'),
      ),
      el('h1', {}, doc.title),
      el(
        'div',
        { class: 'doc-meta' },
        el('span', {}, doc.author || '未知 UP 主'),
        el('span', {}, 'Bilibili'),
        el('span', {}, formatDuration(doc.duration)),
        el('span', {}, doc.content_type || '其他'),
        el('span', {}, fmtDate(doc.created_at)),
        doc.tags && doc.tags.length ? el('span', {}, doc.tags.join(' · ')) : null,
      ),
    ),
  );
  root.append(head);

  const actions = el(
    'div',
    { class: 'doc-actions' },
    el(
      'button',
      {
        class: 'btn small',
        onclick: async () => {
          try {
            await api.patch(`/api/documents/${doc.id}`, { starred: !doc.starred });
            reload();
          } catch (error) {
            errorToast(error);
          }
        },
      },
      doc.starred ? '★ 取消星标' : '☆ 加星标',
    ),
    el('button', { class: 'btn small', onclick: () => editDialog(doc, reload) }, '编辑'),
    el('button', { class: 'btn small', onclick: () => regenerateDialog(doc, state.templates, () => (location.hash = '#/tasks')) }, '重新生成'),
    el('button', { class: 'btn small', onclick: () => assistDialog(doc, reload) }, 'AI 修改'),
    el('button', { class: 'btn small', onclick: () => openChat(doc) }, '对话'),
    el('button', { class: 'btn small', onclick: () => tagDialog(doc, reload) }, '标签'),
    el('button', { class: 'btn small', onclick: () => categoryDialog(doc, reload).catch(errorToast) }, '归类'),
    doc.has_previous_version
      ? el(
          'button',
          {
            class: 'btn small',
            onclick: async () => {
              try {
                await api.post(`/api/documents/${doc.id}/version/restore`, {});
                toast('已恢复上一版');
                reload();
              } catch (error) {
                errorToast(error);
              }
            },
          },
          '恢复上一版',
        )
      : null,
    el('div', { class: 'spacer' }),
    el(
      'button',
      {
        class: 'btn small danger',
        onclick: async () => {
          const confirmed = await window.confirm(`删除《${doc.title}》？正文文件会放入回收站。`);
          if (!confirmed) return;
          try {
            await api.del(`/api/documents/${doc.id}`);
            toast('已删除');
            location.hash = '#/home';
          } catch (error) {
            errorToast(error);
          }
        },
      },
      '删除',
    ),
  );
  root.append(actions);

  const body = el('div', { class: 'doc-body', html: doc.html || '' });
  root.append(body);
  renderMath(body);
  body.querySelectorAll('a').forEach((link) => {
    if (!link.getAttribute('href')?.startsWith('#')) {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noreferrer');
    }
  });

  const status = el('span', { class: 'muted small' }, '');
  const noteInput = el('textarea', { placeholder: '记录自己的想法，自动保存；重新生成总结不会影响备注' });
  noteInput.value = doc.note || '';
  noteInput.addEventListener(
    'input',
    debounce(async () => {
      status.textContent = '保存中…';
      try {
        await api.put(`/api/documents/${doc.id}/note`, { content: noteInput.value });
        status.textContent = '已保存';
      } catch (error) {
        status.textContent = '保存失败';
      }
    }, 800),
  );
  root.append(
    el(
      'div',
      { class: 'note-box' },
      el('div', { class: 'row' }, el('h3', {}, '个人备注'), el('div', { class: 'spacer' }), status),
      noteInput,
    ),
  );
}
