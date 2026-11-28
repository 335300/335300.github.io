/** Typed wrapper around the `window.api` bridge exposed by preload.js. */

interface Bridge {
  get<T>(endpoint: string): Promise<T>;
  post<T>(endpoint: string, body?: unknown): Promise<T>;
  put<T>(endpoint: string, body?: unknown): Promise<T>;
  patch<T>(endpoint: string, body?: unknown): Promise<T>;
  del<T>(endpoint: string): Promise<T>;
}

export interface SavedFile {
  saved: boolean;
  name?: string;
  error?: string;
}
export interface OpenedFile {
  name: string;
  content_base64: string;
  error?: string;
}

declare global {
  interface Window {
    api: Bridge;
    files: {
      save(filename: string, contentBase64: string): Promise<SavedFile>;
      open(extensions?: string[]): Promise<OpenedFile | null>;
    };
  }
}

/** Hand a file the backend made to the macOS Save window. */
export const saveFile = (file: { filename: string; content_base64: string }) =>
  window.files.save(file.filename, file.content_base64);

/** Let the user pick one file with the macOS Open window. */
export const openFile = (extensions?: string[]) => window.files.open(extensions);

export const api: Bridge = {
  get: (e) => window.api.get(e),
  post: (e, b) => window.api.post(e, b),
  put: (e, b) => window.api.put(e, b),
  patch: (e, b) => window.api.patch(e, b),
  del: (e) => window.api.del(e),
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    // Electron prefixes errors that cross the IPC bridge; strip that noise.
    return error.message.replace(/^Error invoking remote method '[^']+': (Error: )?/, '');
  }
  return String(error);
}

export const enc = encodeURIComponent;
