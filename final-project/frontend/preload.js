'use strict';

/**
 * The only bridge between the page and the outside world.
 *
 * The page gets a small, fixed surface: five HTTP verbs against the local
 * backend. It cannot reach Node, the filesystem or any other URL. The request
 * itself is made by the main process, which holds the port and the token.
 */

const { contextBridge, ipcRenderer } = require('electron');

async function request(method, endpoint, body) {
  const { ok, status, data } = await ipcRenderer.invoke('api:request', { method, endpoint, body });
  if (!ok) {
    // FastAPI reports validation errors as a list; flatten to one readable line.
    let detail = data && data.detail;
    if (Array.isArray(detail)) {
      detail = detail
        .map((d) => {
          const field = (d.loc || []).filter((p) => p !== 'body').join('.');
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join('; ');
    }
    const error = new Error(detail || `Request failed (${status})`);
    error.status = status;
    throw error;
  }
  return data;
}

// Files only through the macOS Save / Open windows (see main.js).
contextBridge.exposeInMainWorld('files', {
  save: (filename, contentBase64) => ipcRenderer.invoke('file:save', { filename, content_base64: contentBase64 }),
  open: (extensions) => ipcRenderer.invoke('file:open', { extensions }),
});

contextBridge.exposeInMainWorld('api', {
  get: (endpoint) => request('GET', endpoint),
  post: (endpoint, body) => request('POST', endpoint, body ?? {}),
  put: (endpoint, body) => request('PUT', endpoint, body ?? {}),
  patch: (endpoint, body) => request('PATCH', endpoint, body ?? {}),
  del: (endpoint) => request('DELETE', endpoint),
});
