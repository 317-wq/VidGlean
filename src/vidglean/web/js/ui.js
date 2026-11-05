// 通用 UI 工具
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'html') node.innerHTML = value;
    else if (key === 'value') node.value = value;
    else if (key === 'checked') node.checked = Boolean(value);
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, value === true ? '' : value);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(4)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

let toastTimer = null;
export function toast(message, type = 'info') {
  const wrap = document.getElementById('toast');
  const node = el('div', { class: `toast ${type}` }, message);
  wrap.append(node);
  setTimeout(() => node.remove(), 3600);
  if (toastTimer) clearTimeout(toastTimer);
}

export function errorToast(error) {
  const text = error && error.message ? error.message : String(error);
  toast(text, 'error');
}

export function modal({ title, body, footer, width, onClose }) {
  const root = document.getElementById('modal-root');
  const mask = el('div', { class: 'mask' });
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    mask.remove();
    if (onClose) onClose();
  };
  const dialog = el(
    'div',
    { class: 'modal', style: width ? `width:${width}` : '' },
    el('header', {}, title),
    el('div', { class: 'body' }, body),
    footer === false ? null : el('footer', {}, ...(footer || [])),
  );
  mask.append(dialog);
  mask.addEventListener('click', (event) => {
    if (event.target === mask) close();
  });
  root.append(mask);
  return { close, dialog };
}

export function confirmDialog(text, { okText = '确定', danger = false } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      handle.close();
      resolve(value);
    };
    const handle = modal({
      title: '请确认',
      width: '440px',
      body: el('div', {}, text),
      onClose: () => finish(false),
      footer: [
        el('button', { class: 'btn', onclick: () => finish(false) }, '取消'),
        el(
          'button',
          { class: `btn ${danger ? 'danger' : 'primary'}`, onclick: () => finish(true) },
          okText,
        ),
      ],
    });
  });
}

export function fmtDate(value) {
  if (!value) return '';
  return String(value).replace('T', ' ').slice(0, 16);
}

export function fmtSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export const STATUS_TEXT = {
  pending: '等待中',
  running: '处理中',
  paused: '已暂停',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
  interrupted: '已中断',
};

export function statusBadge(status) {
  const cls = status === 'succeeded' ? 'ok' : status === 'failed' ? 'err' : status === 'running' ? '' : '';
  return el('span', { class: `badge ${cls}` }, STATUS_TEXT[status] || status);
}

export function debounce(fn, delay = 300) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export function renderMath(container) {
  if (typeof window.renderMathInElement !== 'function') return;
  try {
    window.renderMathInElement(container, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true },
      ],
      throwOnError: false,
    });
  } catch (error) {
    console.warn('公式渲染失败', error);
  }
}

export function emptyState(text) {
  return el('div', { class: 'empty' }, text);
}
