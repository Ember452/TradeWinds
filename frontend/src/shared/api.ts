// 统一 API 客户端:JWT 注入、401 统一处理、{code,message} 错误体解析

const TOKEN_KEY = "tradewinds_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...options, headers, body: JSON.stringify(options.body) });

  if (response.status === 401) {
    // token 缺失/过期:统一清除并回到登录页,由路由守卫接管后续
    setToken(null);
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "auth_failed", "登录已过期,请重新登录");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { code?: string; message?: string };
    throw new ApiError(response.status, payload.code ?? "unknown", payload.message ?? response.statusText);
  }
  return (await response.json()) as T;
}

/** SSE 流式 POST:fetch 流式读取(POST 无法用 EventSource)。 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json", Accept: "text/event-stream" });
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    const payload = (await response.json().catch(() => ({}))) as { code?: string; message?: string };
    throw new ApiError(response.status, payload.code ?? "unknown", payload.message ?? response.statusText);
  }

  // 解析 SSE 帧:空行分隔,event:/data: 成对出现
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index !== -1) {
      const frame = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const parsed = parseFrame(frame);
      if (parsed) onEvent(parsed.type, parsed.data);
      index = buffer.indexOf("\n\n");
    }
  }
}

function parseFrame(frame: string): { type: string; data: Record<string, unknown> } | null {
  let type = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!type) return null;
  return { type, data: JSON.parse(data) as Record<string, unknown> };
}
