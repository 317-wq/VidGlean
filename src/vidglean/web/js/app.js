import { api, eventSource } from './api.js';
import {
  confirmDialog,
  debounce,
  el,
  errorToast,
  modal,
  toast,
} from './ui.js';
import { openImportPanel, renderHome } from './views/home.js';
import { renderDoc } from './views/doc.js';
import { renderTasks } from './views/tasks.js';
import { renderSettings } from './views/settings.js';

export const state = {
  q: '',
  view: 'home',
  starred: false,
  category: null,
  listMode: localStorage.getItem('vg-list-mode') || 'grid',
  health: null,
  settings: null,
  categories: [],
  templates: [],
  docId: '',
};

const viewEl = document.getElementById('view');
const searchEl = document.getElementById('search');

function parseHash() {
  const raw = (location.hash || '#/home').replace(/^#\/?/, '');
  const parts = raw.split('/').filter(Boolean);
  return { view: parts[0] || 'home', id: parts[1] || '' };
}

function setNavActive(view) {
  document.querySelectorAll('.nav a').forEach((link) => {
    const target = link.dataset.nav;
    const active = target === view || (view === 'doc' && target === 'home');
    link.classList.toggle('active', active);
  });
}

export async function loadCategories() {
  try {
    const data = await api.get('/api/categories');
    state.categories = data.items;
    renderSidebarCategories();
  } catch (error) {
    console.warn(error);
  }
}

function selectCategory(categoryId) {
  state.category = state.category === categoryId ? null : categoryId;
  state.q = '';
  searchEl.value = '';
  if (parseHash().view !== 'home' && parseHash().view !== 'starred') {
    location.hash = '#/home';
  } else {
    render();
  }
}

function nameDialog({ title, value = '', okText, onSubmit }) {
  const input = el('input', { class: 'field', value, placeholder: '分类名称' });
  const submit = async () => {
    const name = input.value.trim();
    if (!name) {
      input.focus();
      return;
    }
    try {
      await onSubmit(name);
      handle.close();
    } catch (error) {
      errorToast(error);
    }
  };
  const handle = modal({
    title,
    width: '420px',
    body: input,
    footer: [
      el('button', { class: 'btn', onclick: () => handle.close() }, '取消'),
      el('button', { class: 'btn primary', onclick: submit }, okText),
    ],
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.isComposing) {
      event.preventDefault();
      submit();
    }
  });
  setTimeout(() => {
    input.focus();
    input.select();
  }, 30);
}

async function renameCategory(category) {
  nameDialog({
    title: '重命名分类',
    value: category.name,
    okText: '保存',
    onSubmit: async (name) => {
      await api.patch(`/api/categories/${category.id}`, { name });
      await loadCategories();
      toast('已重命名');
    },
  });
}

async function deleteCategory(category) {
  const confirmed = await confirmDialog(
    `删除分类「${category.name}」？只会解除文档与它的关联，文档不会被删除。`,
    { okText: '删除', danger: true },
  );
  if (!confirmed) return;
  try {
    await api.del(`/api/categories/${category.id}`);
    if (state.category === category.id) state.category = null;
    await loadCategories();
    toast('分类已删除');
    render();
  } catch (error) {
    errorToast(error);
  }
}

function renderSidebarCategories() {
  const list = document.getElementById('cat-list');
  list.innerHTML = '';
  for (const category of state.categories) {
    const item = el(
      'li',
      {
        class: state.category === category.id ? 'active' : '',
        onclick: () => selectCategory(category.id),
      },
      el('span', { class: 'cat-name' }, category.name),
      el(
        'span',
        { class: 'cat-actions' },
        el(
          'button',
          {
            class: 'icon-btn',
            title: '重命名',
            onclick: (event) => {
              event.stopPropagation();
              renameCategory(category);
            },
          },
          '✎',
        ),
        el(
          'button',
          {
            class: 'icon-btn danger',
            title: '删除',
            onclick: (event) => {
              event.stopPropagation();
              deleteCategory(category);
            },
          },
          '✕',
        ),
      ),
      el('span', { class: 'count' }, String(category.count || 0)),
    );
    list.append(item);
  }
  if (!state.categories.length) {
    list.append(el('li', { class: 'muted small' }, '还没有分类'));
  }
}

async function loadTemplates() {
  try {
    const data = await api.get('/api/templates');
    state.templates = data.items;
  } catch (error) {
    state.templates = [];
  }
}

async function loadSettings() {
  try {
    state.settings = await api.get('/api/settings');
    const theme = state.settings.theme || 'light';
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('vg-theme', theme);
  } catch (error) {
    state.settings = null;
  }
}

function renderSideFooter() {
  const foot = document.getElementById('side-foot');
  foot.innerHTML = '';
  const health = state.health || {};
  foot.append(
    el('div', {}, `版本 ${health.version || '-'}`),
    el(
      'div',
      { class: health.has_model ? '' : 'warn-text' },
      health.has_model ? '模型已配置' : '未配置模型',
    ),
    el(
      'div',
      { class: health.has_bilibili ? '' : 'warn-text' },
      health.has_bilibili ? 'B 站凭证已配置' : '未配置 B 站凭证',
    ),
  );
}

export async function refreshHealth() {
  try {
    state.health = await api.get('/api/health');
    renderSideFooter();
  } catch (error) {
    // 后端短暂不可用时不打扰用户
  }
}

export async function render() {
  refreshHealth();
  const { view, id } = parseHash();
  state.view = view;
  state.docId = id;
  setNavActive(view);
  searchEl.value = state.q;
  viewEl.innerHTML = '';
  try {
    if (view === 'doc') {
      await renderDoc(viewEl, state, id);
    } else if (view === 'tasks') {
      await renderTasks(viewEl, state);
    } else if (view === 'settings') {
      await renderSettings(viewEl, state);
    } else {
      await renderHome(viewEl, state, view);
    }
  } catch (error) {
    console.error(error);
    viewEl.append(el('div', { class: 'empty' }, error.message || '页面加载失败'));
  }
}

function wireShortcuts() {
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      const masks = document.querySelectorAll('#modal-root .mask');
      if (masks.length) {
        masks[masks.length - 1].remove();
        return;
      }
      const drawer = document.getElementById('chat-drawer');
      if (!drawer.hidden) {
        drawer.hidden = true;
        return;
      }
      if (document.activeElement === searchEl && searchEl.value) {
        searchEl.value = '';
        state.q = '';
        render();
      }
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
      event.preventDefault();
      searchEl.focus();
      searchEl.select();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
      event.preventDefault();
      location.hash = '#/home';
      setTimeout(() => openImportPanel(), 60);
    }
  });
}

function wireEvents() {
  const source = eventSource();
  source.addEventListener('task', (event) => {
    let payload = {};
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    const { view } = parseHash();
    if (view === 'tasks') render();
    if (payload.status === 'succeeded') {
      toast('视频总结已完成');
      if (view === 'home' || view === 'starred') render();
      loadCategories();
    } else if (payload.status === 'failed' && payload.error_code) {
      if (view === 'tasks') render();
    }
  });
  source.addEventListener('document', () => {
    const { view } = parseHash();
    if (view === 'home' || view === 'starred') render();
  });
  source.onerror = () => {
    setTimeout(() => {
      if (source.readyState === EventSource.CLOSED) window.location.reload();
    }, 3000);
  };
}

async function boot() {
  const splashStatus = document.getElementById('splash-status');
  try {
    state.health = await api.get('/api/health');
  } catch (error) {
    splashStatus.textContent = `后端初始化失败：${error.message}`;
    return;
  }
  await loadSettings();
  await Promise.all([loadCategories(), loadTemplates()]);
  renderSideFooter();
  document.getElementById('app').hidden = false;
  document.getElementById('splash').classList.add('hide');
  setTimeout(() => document.getElementById('splash').remove(), 400);

  // 侧边栏折叠状态
  const applySidebar = () => {
    const collapsed = localStorage.getItem('vg-sidebar') === 'collapsed';
    document.getElementById('app').classList.toggle('collapsed', collapsed);
  };
  document.getElementById('btn-collapse').addEventListener('click', () => {
    localStorage.setItem('vg-sidebar', 'collapsed');
    applySidebar();
  });
  document.getElementById('btn-expand').addEventListener('click', () => {
    localStorage.setItem('vg-sidebar', 'open');
    applySidebar();
  });
  applySidebar();

  searchEl.addEventListener(
    'input',
    debounce(() => {
      state.q = searchEl.value.trim();
      const { view } = parseHash();
      if (state.q && view !== 'home' && view !== 'starred') {
        location.hash = '#/home';
      } else if (view === 'home' || view === 'starred') {
        render();
      }
    }, 300),
  );

  document.getElementById('btn-import').addEventListener('click', () => {
    location.hash = '#/home';
    setTimeout(() => openImportPanel(), 60);
  });

  document.getElementById('new-cat').addEventListener('click', () => {
    nameDialog({
      title: '新建分类',
      okText: '创建',
      onSubmit: async (name) => {
        await api.post('/api/categories', { name });
        await loadCategories();
        toast('分类已创建');
      },
    });
  });

  wireShortcuts();
  wireEvents();
  window.addEventListener('hashchange', render);
  // 文档归类、分类增删都可能改到侧边栏，统一用一个事件刷新
  window.addEventListener('vg:categories-changed', () => loadCategories());
  window.addEventListener('vg:health-changed', () => refreshHealth());
  if (!location.hash) location.hash = '#/home';
  await render();
}

boot();
