import { getSessionId } from "./auth";

// 后端 FastAPI 地址，可通过环境变量 NEXT_PUBLIC_API_BASE 覆盖
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type TaskStatus = "pending" | "running" | "success" | "failed";

export interface UploadResult {
  ok: boolean;
  file_id: string;
  original_filename: string;
  size: number;
}

export interface ToolLogEntry {
  tool: string;
  args?: unknown;
  result?: { ok?: boolean; changed?: string[]; message?: string };
}

export interface Report {
  diff?: unknown;
  verification?: {
    ok?: boolean;
    rule_check?: { ok?: boolean; issue_count?: number; issues?: unknown[] };
    structure_check?: unknown;
  };
  tool_log?: ToolLogEntry[];
  changed_count?: number;
  retry_count?: number;
  output_path?: string;
  preview?: unknown;
}

export interface Task {
  id: string;
  session_id: string;
  file_id: string;
  original_filename: string;
  status: TaskStatus;
  progress: number;
  requirements: string;
  format_rules: Record<string, unknown> | null;
  output_path: string | null;
  preview_pdf: string | null;
  preview_png: string | null;
  report: Report | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  estimated_seconds: number | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "X-Session-Id": getSessionId(),
    ...(init?.headers as Record<string, string>) ?? {},
  };
  // credentials: "include" —— 跨域（前端 3000 → 后端 8000）时携带设备凭证 Cookie，
  // 使设备离开局域网后仍可凭凭证访问
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // 非 JSON 响应，保留 statusText
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "X-Session-Id": getSessionId() },
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(res.statusText);
  }
  return res.blob();
}

// ---- File ----
export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>("/api/upload", { method: "POST", body: form });
}

export async function createTask(
  fileId: string,
  requirements: string,
  originalFilename: string = "",
): Promise<{ ok: boolean; task_id: string; status: string }> {
  return request("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId, requirements, original_filename: originalFilename }),
  });
}

export async function getTask(taskId: string): Promise<Task> {
  return request<Task>(`/api/tasks/${taskId}`);
}

export async function undoTask(
  taskId: string,
): Promise<{ ok: boolean; message: string }> {
  return request(`/api/tasks/${taskId}/undo`, { method: "POST" });
}

// ---- Preview / Download (blob, with session header) ----
export async function fetchPreviewBlobUrl(
  taskId: string,
  type: "png" | "pdf" = "png",
): Promise<string> {
  const blob = await requestBlob(`/api/tasks/${taskId}/preview?type=${type}`);
  return URL.createObjectURL(blob);
}

export async function downloadFile(taskId: string, originalFilename: string = ""): Promise<void> {
  const blob = await requestBlob(`/api/tasks/${taskId}/download`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const name = originalFilename || `formatted_${taskId}.docx`;
  const dot = name.lastIndexOf(".");
  a.download = dot > 0 ? `${name.slice(0, dot)}_修改版${name.slice(dot)}` : `${name}_修改版.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}