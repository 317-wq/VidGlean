import { api, TOKEN } from '../api.js';
import { el, errorToast, fmtSize, modal, toast } from '../ui.js';

async function saveSettings(values) {
  const data = await api.put('/api/settings', { values });
  if (values.theme) {
    document.documentElement.dataset.theme = values.theme;
    localStorage.setItem('vg-theme', values.theme);
  }
  return data;
}

function row(label, control, hint) {
  return [
    el('label', {}, label),
    el('div', {}, control, hint ? el('div', { class: 'muted small', style: 'margin-top:4px' }, hint) : null),
  ];
}

function section(title, hint, ...children) {
  return el(
    'section',
    { class: 'card settings-section' },
    el('h2', {}, title),
    hint ? el('div', { class: 'hint' }, hint) : null,
    ...children,
  );
}

// ---------------------------------------------------------------- 通用

async function generalTab(settings) {
  const theme = el(
    'select',
    { class: 'field' },
    el('option', { value: 'light' }, '浅色'),
    el('option', { value: 'dark' }, '深色'),
    el('option', { value: 'soft' }, '柔和蓝粉紫'),
  );
  theme.value = settings.theme || 'light';
  theme.addEventListener('change', () => saveSettings({ theme: theme.value }).catch(errorToast));

  const depth = el(
    'select',
    { class: 'field' },
    el('option', { value: 'auto' }, '自动（由内容决定）'),
    el('option', { value: 'brief' }, '简洁'),
    el('option', { value: 'standard' }, '标准'),
    el('option', { value: 'detailed' }, '详细'),
  );
  depth.value = settings.depth || 'auto';
  depth.addEventListener('change', () => saveSettings({ depth: depth.value }).catch(errorToast));

  const videoConc = el('input', { class: 'field', type: 'number', min: '1', max: '8', value: settings.concurrency_video });
  const aiConc = el('input', { class: 'field', type: 'number', min: '1', max: '8', value: settings.concurrency_ai });
  for (const input of [videoConc, aiConc]) {
    input.addEventListener('change', () => {
      saveSettings({
        concurrency_video: Number(videoConc.value) || 2,
        concurrency_ai: Number(aiConc.value) || 2,
      }).catch(errorToast);
    });
  }

  const retries = el('input', { class: 'field', type: 'number', min: '0', max: '10', value: settings.max_retries });
  retries.addEventListener('change', () => saveSettings({ max_retries: Number(retries.value) || 0 }).catch(errorToast));

  const retention = el('input', { class: 'field', type: 'number', min: '1', max: '365', value: settings.log_retention_days });
  retention.addEventListener('change', () => saveSettings({ log_retention_days: Number(retention.value) || 30 }).catch(errorToast));

  const notify = el('input', { type: 'checkbox', checked: Boolean(settings.notify) });
  notify.addEventListener('change', () => saveSettings({ notify: notify.checked }).catch(errorToast));

  return section(
    '通用',
    '主题、并发与重试策略。修改后立即生效。',
    el(
      'div',
      { class: 'form-grid' },
      ...row('主题', theme),
      ...row('默认总结深度', depth),
      ...row('视频任务并发数', videoConc, '同时处理的视频任务数量'),
      ...row('AI 请求并发数', aiConc, '同时发出的模型请求数量'),
      ...row('自动重试次数', retries, '临时性错误（超时、限流）自动重试的最大次数'),
      ...row('日志保留天数', retention),
      ...row('完成时通知', notify, '任务完成后在软件内弹出提示'),
    ),
  );
}

// ---------------------------------------------------------------- 模型

function modelDialog(existing, onSaved) {
  const name = el('input', { class: 'field', value: existing ? existing.name : '', placeholder: '例如：DeepSeek' });
  const baseUrl = el('input', {
    class: 'field',
    value: existing ? existing.base_url : 'https://api.deepseek.com/v1',
    placeholder: 'https://api.example.com/v1',
  });
  const model = el('input', { class: 'field', value: existing ? existing.model : '', placeholder: 'deepseek-chat' });
  const apiKey = el('input', { class: 'field', type: 'password', placeholder: existing ? '留空表示不修改' : 'API Key' });
  const temperature = el('input', { class: 'field', type: 'number', step: '0.1', min: '0', max: '2', value: existing ? existing.temperature : 0.5 });
  const maxTokens = el('input', { class: 'field', type: 'number', value: existing ? existing.max_tokens : 8192 });
  const timeout = el('input', { class: 'field', type: 'number', value: existing ? existing.timeout : 120 });

  const handle = modal({
    title: existing ? '编辑模型' : '添加模型',
    width: '620px',
    body: el(
      'div',
      { class: 'form-grid' },
      ...row('名称', name),
      ...row('Base URL', baseUrl),
      ...row('模型名', model),
      ...row('API Key', apiKey, '保存在 Windows 凭据管理器中'),
      ...row('Temperature', temperature),
      ...row('Max Tokens', maxTokens),
      ...row('超时（秒）', timeout),
    ),
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            const payload = {
              name: name.value.trim(),
              base_url: baseUrl.value.trim(),
              model: model.value.trim(),
              temperature: Number(temperature.value) || 0.5,
              max_tokens: Number(maxTokens.value) || 4096,
              timeout: Number(timeout.value) || 120,
            };
            try {
              if (existing) {
                if (apiKey.value.trim()) payload.api_key = apiKey.value.trim();
                await api.patch(`/api/models/${existing.id}`, payload);
              } else {
                payload.api_key = apiKey.value.trim();
                await api.post('/api/models', payload);
              }
              handle.close();
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
}

async function modelsTab() {
  const data = await api.get('/api/models');
  const list = el('div', {});
  if (!data.items.length) {
    list.append(el('div', { class: 'muted small' }, '还没有模型，先添加一个 OpenAI 兼容服务。'));
  }
  for (const item of data.items) {
    list.append(
      el(
        'div',
        { class: 'model-row' },
        el(
          'div',
          { style: 'flex:1;min-width:0' },
          el('div', { class: 'name' }, item.name, item.is_current ? el('span', { class: 'badge ok', style: 'margin-left:8px' }, '当前使用') : null),
          el('div', { class: 'muted small' }, `${item.model} · ${item.base_url}`),
          item.has_key ? null : el('div', { class: 'badge err', style: 'margin-top:4px' }, '缺少 API Key'),
        ),
        el(
          'div',
          { class: 'row' },
          item.is_current
            ? null
            : el(
                'button',
                {
                  class: 'btn small',
                  onclick: async () => {
                    try {
                      await api.post(`/api/models/${item.id}/current`, {});
                      toast('已切换模型');
                      rerender();
                    } catch (error) {
                      errorToast(error);
                    }
                  },
                },
                '设为当前',
              ),
          el(
            'button',
            {
              class: 'btn small',
              onclick: async () => {
                try {
                  const result = await api.post(`/api/models/${item.id}/test`, {});
                  if (result.ok) toast(`连接正常：${result.reply || 'OK'}`);
                  else toast(result.error.message || '连接失败', 'error');
                } catch (error) {
                  errorToast(error);
                }
              },
            },
            '测试',
          ),
          el('button', { class: 'btn small', onclick: () => modelDialog(item, rerender) }, '编辑'),
          el(
            'button',
            {
              class: 'btn small danger',
              onclick: async () => {
                if (!window.confirm(`删除模型「${item.name}」？`)) return;
                try {
                  await api.del(`/api/models/${item.id}`);
                  rerender();
                } catch (error) {
                  errorToast(error);
                }
              },
            },
            '删除',
          ),
        ),
      ),
    );
  }
  const container = section(
    'AI 模型',
    '第一版只支持 OpenAI 兼容接口，API Key 保存在系统凭据管理器。',
    list,
    el('div', { style: 'margin-top:12px' }, el('button', { class: 'btn primary', onclick: () => modelDialog(null, rerender) }, '添加模型')),
  );
  function rerender() {
    renderSettings(document.getElementById('view'), null, 'models');
  }
  return container;
}

// ---------------------------------------------------------------- 模板

async function templatesTab() {
  const data = await api.get('/api/templates');
  const list = el('div', {});
  for (const item of data.items) {
    list.append(
      el(
        'div',
        { class: 'template-row' },
        el(
          'div',
          { style: 'flex:1;min-width:0' },
          el(
            'div',
            { class: 'name' },
            item.name,
            item.kind === 'builtin' ? el('span', { class: 'badge', style: 'margin-left:8px' }, '内置') : null,
            item.is_default ? el('span', { class: 'badge ok', style: 'margin-left:8px' }, '默认') : null,
          ),
          el('div', { class: 'muted small' }, item.description || ''),
        ),
        el(
          'div',
          { class: 'row' },
          item.is_default
            ? null
            : el(
                'button',
                {
                  class: 'btn small',
                  onclick: async () => {
                    try {
                      await api.post(`/api/templates/${item.id}/default`, {});
                      toast('已设为默认模板');
                      rerender();
                    } catch (error) {
                      errorToast(error);
                    }
                  },
                },
                '设为默认',
              ),
          item.kind === 'custom'
            ? el(
                'button',
                {
                  class: 'btn small danger',
                  onclick: async () => {
                    if (!window.confirm(`删除模板「${item.name}」？已生成的文档不受影响。`)) return;
                    try {
                      await api.del(`/api/templates/${item.id}`);
                      rerender();
                    } catch (error) {
                      errorToast(error);
                    }
                  },
                },
                '删除',
              )
            : null,
        ),
      ),
    );
  }

  const container = section(
    'Markdown 模板',
    '可用变量：{{video_title}} {{author}} {{platform}} {{url}} {{duration}} {{date}} {{content_type}} {{extra}} {{depth}}',
    list,
    el('div', { style: 'margin-top:12px' }, el('button', { class: 'btn primary', onclick: uploadTemplate }, '上传自定义模板')),
  );
  function rerender() {
    renderSettings(document.getElementById('view'), null, 'templates');
  }
  return container;
}

function uploadTemplate() {
  const name = el('input', { class: 'field', placeholder: '模板名称' });
  const description = el('input', { class: 'field', placeholder: '一句话说明适用场景' });
  const textarea = el('textarea', { class: 'field code', rows: '14', placeholder: '粘贴 Markdown 模板内容' });
  const file = el('input', { type: 'file', accept: '.md,text/markdown' });
  file.addEventListener('change', () => {
    const selected = file.files && file.files[0];
    if (!selected) return;
    const reader = new FileReader();
    reader.onload = () => {
      textarea.value = String(reader.result || '');
      if (!name.value) name.value = selected.name.replace(/\.md$/i, '');
    };
    reader.readAsText(selected, 'utf-8');
  });
  const handle = modal({
    title: '上传 Markdown 模板',
    width: '700px',
    body: el('div', {}, name, el('div', { style: 'margin-top:10px' }, description), el('div', { style: 'margin-top:10px' }, file), el('div', { style: 'margin-top:10px' }, textarea)),
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            try {
              await api.post('/api/templates', {
                name: name.value.trim(),
                description: description.value.trim(),
                content: textarea.value,
              });
              handle.close();
              toast('模板已上传');
              renderSettings(document.getElementById('view'), null, 'templates');
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '上传',
      ),
    ],
  });
}

// ---------------------------------------------------------------- B 站

async function bilibiliTab() {
  const data = await api.get('/api/bilibili/credential');
  const input = el('input', { class: 'field', type: 'password', placeholder: '粘贴 SESSDATA 的值' });
  const status = el('div', { class: 'muted small' }, data.configured ? '已配置' : '未配置（无凭证通常拿不到字幕）');
  return section(
    'B 站凭证',
    '获取字幕需要登录态。凭证保存在系统凭据管理器，不会写入数据库与日志。',
    status,
    el('div', { style: 'margin-top:12px;max-width:560px' }, input),
    el(
      'div',
      { class: 'row', style: 'margin-top:12px' },
      el(
        'button',
        {
          class: 'btn primary',
          onclick: async () => {
            try {
              await api.put('/api/bilibili/credential', { sessdata: input.value.trim() });
              input.value = '';
              status.textContent = '已配置';
              toast('凭证已保存');
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '保存',
      ),
      el(
        'button',
        {
          class: 'btn danger',
          onclick: async () => {
            if (!window.confirm('清除已保存的 B 站凭证？')) return;
            try {
              await api.del('/api/bilibili/credential');
              status.textContent = '未配置';
              toast('已清除');
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '清除',
      ),
    ),
  );
}

// ---------------------------------------------------------------- 数据

async function dataTab(settings) {
  const dirInput = el('input', { class: 'field', value: settings.data_dir, placeholder: '新的数据目录绝对路径' });
  const backupPath = el('input', { class: 'field', placeholder: '留空则保存在数据目录下' });
  const backupPassword = el('input', { class: 'field', type: 'password', placeholder: '可选：加密密码' });
  const restorePath = el('input', { class: 'field', placeholder: '备份文件绝对路径' });
  const restorePassword = el('input', { class: 'field', type: 'password', placeholder: '如果备份已加密，填写密码' });

  return el(
    'div',
    {},
    section(
      '数据目录',
      `当前目录：${settings.data_dir}`,
      dirInput,
      el(
        'div',
        { class: 'row', style: 'margin-top:12px' },
        el(
          'button',
          {
            class: 'btn',
            onclick: async () => {
              const target = dirInput.value.trim();
              if (!target) return;
              if (!window.confirm('迁移数据到新目录？旧目录会保留，确认无误后可手动删除。')) return;
              try {
                const data = await api.post('/api/system/data-dir', { path: target });
                toast(`已迁移到 ${data.data_dir}，重启后完全生效`);
              } catch (error) {
                errorToast(error);
              }
            },
          },
          '迁移数据',
        ),
      ),
    ),
    section(
      '备份与恢复',
      '备份包含数据库、Markdown 文档、字幕与自定义模板；API Key 不在备份中。',
      el('div', { class: 'muted small', style: 'margin-bottom:8px' }, '备份到'),
      backupPath,
      el('div', { style: 'margin-top:10px' }, backupPassword),
      el(
        'div',
        { class: 'row', style: 'margin-top:10px' },
        el(
          'button',
          {
            class: 'btn primary',
            onclick: async () => {
              try {
                const data = await api.post('/api/backup', {
                  path: backupPath.value.trim(),
                  password: backupPassword.value,
                });
                toast(`已备份：${data.path}（${fmtSize(data.size)}）`);
              } catch (error) {
                errorToast(error);
              }
            },
          },
          '立即备份',
        ),
      ),
      el('div', { class: 'muted small', style: 'margin:18px 0 8px' }, '从备份恢复（会覆盖当前数据，恢复前自动留一份安全备份）'),
      restorePath,
      el('div', { style: 'margin-top:10px' }, restorePassword),
      el(
        'div',
        { class: 'row', style: 'margin-top:10px' },
        el(
          'button',
          {
            class: 'btn danger',
            onclick: async () => {
              const path = restorePath.value.trim();
              if (!path) return;
              if (!window.confirm('确认从该备份恢复？当前数据会被覆盖。')) return;
              try {
                const data = await api.post('/api/restore', { path, password: restorePassword.value });
                toast(`恢复完成${data.safety_backup ? `，安全备份：${data.safety_backup}` : ''}`);
              } catch (error) {
                errorToast(error);
              }
            },
          },
          '恢复',
        ),
      ),
    ),
    section(
      '清理临时文件',
      '清理音频与任务中间产物，不会删除文档、字幕与配置。',
      el(
        'button',
        {
          class: 'btn',
          onclick: async () => {
            try {
              const data = await api.post('/api/system/cleanup', {});
              toast(`已清理 ${data.removed} 项，释放 ${fmtSize(data.freed)}`);
            } catch (error) {
              errorToast(error);
            }
          },
        },
        '立即清理',
      ),
    ),
  );
}

// ---------------------------------------------------------------- 用量

async function usageTab(settings) {
  const data = await api.get('/api/stats/usage?days=30');
  const totals = data.totals || {};
  const rows = (data.daily || []).map((item) =>
    el(
      'tr',
      {},
      el('td', {}, item.day),
      el('td', {}, item.kind === 'summary' ? '总结' : item.kind === 'chat' ? '对话' : '修改'),
      el('td', {}, `${item.calls}`),
      el('td', {}, `${item.prompt_tokens || 0}`),
      el('td', {}, `${item.completion_tokens || 0}`),
      el('td', {}, `${item.total_tokens || 0}`),
    ),
  );

  const updateUrl = el('input', { class: 'field', value: settings.update_url || '', placeholder: 'https://example.com/vidglean/latest.json' });
  updateUrl.addEventListener('change', () => saveSettings({ update_url: updateUrl.value.trim() }).catch(errorToast));

  return el(
    'div',
    {},
    section(
      'Token 与费用',
      '用量来自模型返回的 usage；无法获取时按 0 记录。',
      el(
        'div',
        { class: 'row', style: 'margin-bottom:14px' },
        el('div', { class: 'card', style: 'padding:12px 16px' }, el('div', { class: 'muted small' }, '累计调用'), el('div', { style: 'font-size:20px;font-weight:600' }, `${totals.calls || 0}`)),
        el('div', { class: 'card', style: 'padding:12px 16px' }, el('div', { class: 'muted small' }, '累计 Token'), el('div', { style: 'font-size:20px;font-weight:600' }, `${totals.total_tokens || 0}`)),
      ),
      rows.length
        ? el(
            'table',
            { class: 'task-table' },
            el('thead', {}, el('tr', {}, el('th', {}, '日期'), el('th', {}, '类型'), el('th', {}, '次数'), el('th', {}, '输入'), el('th', {}, '输出'), el('th', {}, '合计'))),
            el('tbody', {}, ...rows),
          )
        : el('div', { class: 'muted small' }, '最近 30 天没有调用记录'),
    ),
    section(
      '日志与更新',
      '导出的日志会自动过滤 API Key 与 SESSDATA。',
      el(
        'div',
        { class: 'row' },
        el('a', { class: 'btn', href: `/api/logs${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`, target: '_blank' }, '下载日志'),
        el(
          'button',
          {
            class: 'btn',
            onclick: async () => {
              try {
                const result = await api.post('/api/update/check', {});
                toast(result.available ? `发现新版本 ${result.latest}` : result.message || '已是最新版本');
              } catch (error) {
                errorToast(error);
              }
            },
          },
          '检查更新',
        ),
      ),
      el('div', { class: 'muted small', style: 'margin:14px 0 6px' }, '更新源地址（JSON：version / notes / url）'),
      updateUrl,
    ),
  );
}

// ---------------------------------------------------------------- 入口

const TABS = [
  { key: 'general', label: '通用' },
  { key: 'models', label: '模型' },
  { key: 'templates', label: '模板' },
  { key: 'bilibili', label: 'B 站' },
  { key: 'data', label: '数据' },
  { key: 'usage', label: '用量与日志' },
];

async function renderSettings(root, state, tab = 'general') {
  root.innerHTML = '';
  root.append(
    el(
      'div',
      { class: 'page-head' },
      el('h1', {}, '设置'),
      el('span', { class: 'muted small' }, '所有设置自动保存'),
    ),
  );
  const settings = await api.get('/api/settings');
  const tabs = el('div', { class: 'settings-tabs' });
  for (const item of TABS) {
    tabs.append(
      el(
        'button',
        {
          class: item.key === tab ? 'active' : '',
          onclick: () => renderSettings(root, state, item.key),
        },
        item.label,
      ),
    );
  }
  root.append(tabs);

  const panel = el('div', {});
  root.append(panel);
  try {
    if (tab === 'models') panel.append(await modelsTab());
    else if (tab === 'templates') panel.append(await templatesTab());
    else if (tab === 'bilibili') panel.append(await bilibiliTab());
    else if (tab === 'data') panel.append(await dataTab(settings));
    else if (tab === 'usage') panel.append(await usageTab(settings));
    else panel.append(await generalTab(settings));
  } catch (error) {
    panel.append(el('div', { class: 'empty' }, error.message));
  }
}

export { renderSettings };
