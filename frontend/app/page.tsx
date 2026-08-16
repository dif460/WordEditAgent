"use client";

/* ============================================================
 * Word 格式 Agent —— 前端工作台（高端商务极简风格）
 * ------------------------------------------------------------
 * 布局：顶部精简工具栏 + 左侧可折叠文件导航 + 中央白纸画布 + 右侧属性面板
 * 说明：本文件仅重构界面样式、布局与组件外观；
 *       全部业务逻辑（上传/创建任务/轮询/撤销/下载/预览）与 API 调用原样保留。
 * ============================================================ */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, PointerEvent as ReactPointerEvent, ReactNode } from "react";
import {
  createTask,
  downloadFile,
  fetchPreviewBlobUrl,
  getTask,
  type Task,
  type ToolLogEntry,
  undoTask,
  uploadFile,
} from "@/lib/api";

const EXAMPLE_REQUIREMENT =
  "标题黑体三号，正文宋体小四，1.5倍行距，首行缩进2字符";

const STATUS_TEXT: Record<Task["status"], string> = {
  pending: "排队中",
  running: "处理中",
  success: "已完成",
  failed: "失败",
};

/* ============================================================
 * 纯 UI 工具函数
 * ============================================================ */

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} 秒`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  return `${m} 分 ${rs} 秒`;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** 从任务 format_rules 提取字体/段落摘要（仅展示用，不参与业务逻辑） */
function ruleSummary(task: Task | null) {
  const body = task?.format_rules?.body as
    | {
        font?: string;
        size?: number | string;
        line_spacing?: number | string;
        first_line_indent?: string;
        alignment?: string;
      }
    | undefined;
  const hasRules = !!task?.format_rules;
  const alignText = (a?: string) =>
    a === "justify" ? "两端对齐"
    : a === "center" ? "居中"
    : a === "left" ? "左对齐"
    : a === "right" ? "右对齐"
    : "—";
  return {
    hasRules,
    font: body?.font ?? "—",
    size: body?.size != null ? `${body.size}pt` : "—",
    spacing: body?.line_spacing != null ? `${body.line_spacing}` : "—",
    indent: body?.first_line_indent ?? "—",
    align: body ? alignText(body.alignment) : "—",
  };
}

/* ============================================================
 * 图标（内联 SVG，细线风格，随 currentColor 变色）
 * ============================================================ */

const ICONS: Record<string, ReactNode> = {
  upload: (
    <>
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M5 20h14" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12" />
      <path d="M7 11l5 5 5-5" />
      <path d="M5 20h14" />
    </>
  ),
  file: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
    </>
  ),
  doc: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z" />
      <circle cx="12" cy="12" r="2.6" />
    </>
  ),
  undo: (
    <>
      <path d="M9 7 4 12l5 5" />
      <path d="M4 12h11a5 5 0 0 1 0 10h-2" />
    </>
  ),
  pen: (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
    </>
  ),
  report: (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 9h6M9 13h6M9 17h4" />
    </>
  ),
  x: (
    <>
      <path d="M6 6l12 12M18 6 6 18" />
    </>
  ),
  chevronLeft: <path d="M15 6l-6 6 6 6" />,
  chevronRight: <path d="M9 6l6 6-6 6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  check: <path d="M4.5 12.5l5 5 10-11" />,
  alert: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V13" />
      <path d="M12 16.2v.1" />
    </>
  ),
  font: (
    <>
      <path d="M4 19L10.5 5h3L20 19" />
      <path d="M7 13.5h10" />
    </>
  ),
  paragraph: (
    <>
      <path d="M4 6h16M4 10h16M4 14h10M4 18h10" />
    </>
  ),
  spacing: (
    <>
      <path d="M12 4v16" />
      <path d="M8 8l4-4 4 4M8 16l4 4 4-4" />
    </>
  ),
  sidebar: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </>
  ),
  panel: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
};

function Icon({ name, size = 16, className = "" }: { name: string; size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  );
}

/* ============================================================
 * 基础展示组件
 * ============================================================ */

/** 工具栏小按钮（含活跃状态） */
function ToolButton({
  icon,
  label,
  onClick,
  disabled,
  active,
  title,
}: {
  icon?: string;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title ?? label}
      className={`btn-tool ${active ? "btn-tool-active" : ""}`}
    >
      {icon && <Icon name={icon} size={15} />}
      {label}
    </button>
  );
}

/** 工具栏只读信息块（字体/段落摘要，活跃时淡蓝底标记） */
function ToolChip({ label, value, active }: { label: string; value: string; active: boolean }) {
  return (
    <div
      className={`flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-[12px] transition-colors duration-300 ${
        active ? "border-navy-200 bg-navy-50 text-navy-800" : "border-transparent text-ink-400"
      }`}
    >
      <span className="text-ink-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

/** 状态徽章 */
function StatusBadge({ status }: { status: Task["status"] }) {
  const styles: Record<Task["status"], string> = {
    pending: "bg-ink-100 text-ink-500",
    running: "bg-warn-100 text-warn-600",
    success: "bg-ok-100 text-ok-600",
    failed: "bg-err-100 text-err-600",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${styles[status]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {STATUS_TEXT[status]}
    </span>
  );
}

/** 进度条（弱渐变，低饱和） */
function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
      <div
        className="h-full rounded-full bg-gradient-to-r from-navy-600 to-navy-400 transition-[width] duration-300 ease-out"
        style={{ width: `${Math.max(2, pct)}%` }}
      />
    </div>
  );
}

/** 简洁弹窗 */
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div className="absolute inset-0 bg-ink-950/35 backdrop-blur-[2px]" onClick={onClose} />
      <div className="panel relative flex max-h-[82vh] w-full max-w-2xl flex-col shadow-lift">
        <div className="flex items-center justify-between border-b border-ink-150 px-5 py-3.5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-950">
            <Icon name="report" size={16} className="text-navy-600" />
            {title}
          </h3>
          <button type="button" className="btn-tool" onClick={onClose} title="关闭">
            <Icon name="x" size={16} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

/** 侧栏模块标题（文档 / 最近任务） */
function SectionTitle({ children }: { children: ReactNode }) {
  return <h4 className="section-title">{children}</h4>;
}

/** 属性面板卡片标题（加粗正文） */
function CardTitle({ children }: { children: ReactNode }) {
  return <h4 className="card-title">{children}</h4>;
}

/** 属性面板信息行：标签 + 值 */
function InfoRow({ label, value, active }: { label: string; value: string; active?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[13px] text-ink-400">{label}</span>
      <span
        className={`rounded-md px-2 py-0.5 text-[13px] font-medium ${
          active ? "bg-navy-50 text-navy-800" : "bg-ink-100 text-ink-600"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

/* ============================================================
 * 修改报告（仅调整样式，数据结构与逻辑不变）
 * ============================================================ */

function ReportPanel({ task }: { task: Task }) {
  const report = task.report;
  if (!report) return <p className="text-sm text-ink-400">暂无报告</p>;

  const verification = report.verification;
  const toolLog = report.tool_log ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Metric label="修改段落" value={report.changed_count ?? 0} />
        <Metric label="重试次数" value={report.retry_count ?? 0} />
        <Metric
          label="校验"
          value={verification?.ok ? "通过" : "未通过"}
          tone={verification?.ok ? "good" : "bad"}
        />
      </div>

      {verification?.rule_check && (
        <p className="text-xs text-ink-400">
          规则问题 {verification.rule_check.issue_count ?? 0} 处
        </p>
      )}

      <div>
        <p className="mb-2 text-[13px] font-medium text-ink-700">工具执行日志</p>
        {toolLog.length === 0 ? (
          <p className="text-xs text-ink-400">无操作记录</p>
        ) : (
          <ul className="space-y-2">
            {toolLog.map((entry, i) => (
              <ToolLogItem key={i} entry={entry} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-ok-600"
      : tone === "bad"
        ? "text-err-600"
        : "text-ink-950";
  return (
    <div className="rounded-lg border border-ink-150 bg-ink-50 px-3 py-2.5">
      <p className="text-[11px] text-ink-400">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function ToolLogItem({ entry }: { entry: ToolLogEntry }) {
  const msg = entry.result?.message;
  return (
    <li className="flex items-start gap-2 text-xs">
      <span className="mt-0.5 shrink-0 rounded bg-navy-50 px-1.5 py-0.5 font-mono text-[10px] text-navy-700">
        {entry.tool}
      </span>
      <span className="text-ink-600">{msg ?? "-"}</span>
    </li>
  );
}

/* ============================================================
 * 顶部工具栏（分组：文件 / 字体 / 段落 / 导出 / 撤销重做）
 * ============================================================ */

type TopBarProps = {
  status: Task["status"] | null;
  done: boolean;
  uploading: boolean;
  creating: boolean;
  undoing: boolean;
  hasFile: boolean;
  hasFileId: boolean;
  canUndo: boolean;
  canDownload: boolean;
  hasReport: boolean;
  summary: ReturnType<typeof ruleSummary>;
  sidebarCollapsed: boolean;
  panelCollapsed: boolean;
  onToggleSidebar: () => void;
  onTogglePanel: () => void;
  onPickFile: () => void;
  onCreate: () => void;
  onUndo: () => void;
  onDownload: () => void;
  onPreviewPdf: () => void;
  onExample: () => void;
  onShowReport: () => void;
};

function TopBar(props: TopBarProps) {
  const {
    status, done, uploading, creating, undoing, hasFile, hasFileId,
    canUndo, canDownload, hasReport, summary, sidebarCollapsed, panelCollapsed,
    onToggleSidebar, onTogglePanel, onPickFile, onCreate, onUndo,
    onDownload, onPreviewPdf, onExample, onShowReport,
  } = props;

  return (
    <header className="topbar flex h-14 shrink-0 items-center gap-2 bg-white px-4">
      {/* 品牌区 */}
      <div className="flex items-center gap-3 py-2 pr-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-navy-600 to-navy-900 text-white shadow-soft">
          <Icon name="doc" size={17} />
        </div>
        <div className="leading-tight">
          <p className="text-[15px] font-bold tracking-tight text-ink-950">Word 格式 Agent</p>
          <p className="text-[11px] text-ink-400">智能文档格式化工作台</p>
        </div>
      </div>

      {/* 面板折叠控制 */}
      <button
        type="button"
        className="btn-tool ml-1"
        onClick={onToggleSidebar}
        title={sidebarCollapsed ? "展开文件导航" : "折叠文件导航"}
      >
        <Icon name={sidebarCollapsed ? "chevronRight" : "sidebar"} size={15} />
      </button>

      <div className="mx-1 flex min-w-0 items-center gap-1 overflow-x-auto">
        {/* —— 文件组 —— */}
        <ToolButton
          icon="upload"
          label={uploading ? "上传中…" : "上传文档"}
          onClick={onPickFile}
          disabled={uploading}
          active={hasFile}
          title="选择 .docx 文件"
        />
        <button
          type="button"
          className={`btn h-8 px-3 ${hasFileId ? "btn-primary" : "btn-primary"}`}
          onClick={onCreate}
          disabled={!hasFileId || creating}
          title="创建格式化任务"
        >
          {creating ? "处理中…" : "开始格式化"}
        </button>

        <span className="divider-v" />

        {/* —— 字体组 —— */}
        <ToolChip label="字体" value={summary.font} active={summary.hasRules} />
        <ToolChip label="字号" value={summary.size} active={summary.hasRules} />

        <span className="divider-v" />

        {/* —— 段落组 —— */}
        <ToolChip label="行距" value={summary.spacing} active={summary.hasRules} />
        <ToolChip label="缩进" value={summary.indent} active={summary.hasRules} />
        <ToolChip label="对齐" value={summary.align} active={summary.hasRules} />

        <span className="divider-v" />

        {/* —— 导出组 —— */}
        <button
          type="button"
          className="btn btn-primary h-8 px-3"
          onClick={onDownload}
          disabled={!canDownload}
          title="下载格式化后的 docx"
        >
          <Icon name="download" size={15} />
          导出
        </button>
        <button
          type="button"
          className="btn btn-secondary h-8 px-3"
          onClick={onPreviewPdf}
          disabled={!canDownload}
          title="在新窗口查看 PDF 预览"
        >
          <Icon name="eye" size={15} />
          PDF
        </button>

        <span className="divider-v" />

        {/* —— 撤销重做组 —— */}
        <ToolButton
          icon="undo"
          label={undoing ? "撤销中…" : "撤销上一步"}
          onClick={onUndo}
          disabled={!canUndo}
          active={canUndo}
        />
        <ToolButton icon="pen" label="示例需求" onClick={onExample} title="填入示例格式需求" />
      </div>

      {/* 右侧状态区（与左侧工具栏视觉平衡：统一 8px 圆角 / 高度） */}
      <div className="ml-auto flex shrink-0 items-center gap-2">
        {status && <StatusBadge status={status} />}
        <button
          type="button"
          className="btn btn-secondary h-8 px-3"
          onClick={onShowReport}
          disabled={!hasReport}
          title="查看修改报告"
        >
          <Icon name="report" size={15} />
          修改报告
        </button>
        <span className="hidden h-8 items-center gap-1.5 rounded-md bg-ink-50 px-3 text-[11px] text-ink-500 xl:flex">
          <Icon name="shield" size={13} />
          多用户隔离
        </span>
        <button
          type="button"
          className="btn-tool"
          onClick={onTogglePanel}
          title={panelCollapsed ? "展开属性面板" : "折叠属性面板"}
        >
          <Icon name={panelCollapsed ? "chevronLeft" : "panel"} size={15} />
        </button>
      </div>
    </header>
  );
}

/* ============================================================
 * 左侧文件导航栏（可折叠）
 * ============================================================ */

type SidebarProps = {
  collapsed: boolean;
  width: number;
  dragging: boolean;
  file: File | null;
  fileId: string | null;
  originalFilename: string | null;
  task: Task | null;
  uploading: boolean;
  canUpload: boolean;
  onStartResize: (e: ReactPointerEvent) => void;
  onPickFile: () => void;
  onUpload: () => void;
};

function LeftSidebar(props: SidebarProps) {
  const { collapsed, width, dragging, file, fileId, originalFilename, task, uploading, canUpload, onStartResize, onPickFile, onUpload } = props;

  return (
    <aside
      className="relative flex shrink-0 flex-col overflow-hidden border-r border-ink-150 bg-white"
      style={{
        width: collapsed ? 0 : width,
        minWidth: 0,
        transition: dragging ? "none" : "width 300ms ease",
      }}
    >
      {/* 拖拽调宽手柄（右边缘） */}
      {!collapsed && (
        <div
          onPointerDown={onStartResize}
          className="absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize bg-transparent transition-colors duration-300 hover:bg-navy-200/60"
          title="拖拽调整宽度"
        />
      )}

      <div className="flex min-w-[248px] flex-1 flex-col overflow-y-auto">
        {/* 导航头部 */}
        <div className="flex items-center justify-between px-4 pb-3 pt-5">
          <SectionTitle>文档</SectionTitle>
        </div>

        {/* 当前文档卡片 */}
        <div className="px-4">
          <div className="panel p-4 transition-all duration-300 hover:border-ink-200 hover:shadow-lift">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
                <Icon name="file" size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-ink-800">
                  {originalFilename ?? file?.name ?? "未选择文档"}
                </p>
                <p className="mt-0.5 truncate text-[11px] text-ink-400">
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB`
                    : "点击上传 .docx 文件"}
                </p>
              </div>
            </div>

            {file && (
              <div className="mt-3 flex items-center gap-2">
                {!fileId ? (
                  <button
                    type="button"
                    className="btn btn-primary h-7 flex-1 px-2 text-xs"
                    onClick={onUpload}
                    disabled={!canUpload}
                  >
                    {uploading ? "上传中…" : "上传文件"}
                  </button>
                ) : (
                  <span className="flex h-7 flex-1 items-center gap-1 rounded-md bg-ok-100 px-2 text-xs font-medium text-ok-600">
                    <Icon name="check" size={13} />
                    已上传
                  </span>
                )}
                <button type="button" className="btn-ghost btn h-7 px-2.5 text-xs" onClick={onPickFile}>
                  更换
                </button>
              </div>
            )}

            {fileId && (
              <p className="mt-2 truncate font-mono text-[10px] text-ink-300">file_id: {fileId}</p>
            )}
          </div>
        </div>

        {/* 最近任务 */}
        <div className="mt-7 px-4">
          <SectionTitle>最近任务</SectionTitle>
        </div>
        <div className="mt-2 px-4">
          {task ? (
            <div className="panel p-4 transition-all duration-300 hover:border-ink-200 hover:shadow-lift">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-medium text-ink-800">格式化任务</p>
                <StatusBadge status={task.status} />
              </div>
              {task.status === "running" && (
                <div className="mt-3">
                  <ProgressBar pct={Math.round((task.progress ?? 0) * 100)} />
                </div>
              )}
              <p className="mt-3 flex items-center gap-1 text-[11px] text-ink-400">
                <Icon name="clock" size={12} />
                {task.created_at
                  ? new Date(task.created_at).toLocaleString("zh-CN", { hour12: false })
                  : "—"}
              </p>
            </div>
          ) : (
            <p className="px-1 py-2 text-xs leading-5 text-ink-300">暂无任务，上传文档后开始格式化</p>
          )}
        </div>

        <div className="mt-auto px-5 pb-5 pt-6">
          <p className="flex items-center gap-1.5 text-[11px] text-ink-300">
            <Icon name="shield" size={12} />
            会话数据按设备隔离
          </p>
        </div>
      </div>
    </aside>
  );
}

/* ============================================================
 * 中央画布（浅灰背景 + 白色纸张，模拟真实 A4 白纸）
 * ============================================================ */

type CanvasProps = {
  file: File | null;
  fileId: string | null;
  originalFilename: string | null;
  task: Task | null;
  uploading: boolean;
  creating: boolean;
  progressPct: number;
  elapsed: number;
  previewSrc: string | null;
  error: string | null;
  notice: string | null;
  summary: ReturnType<typeof ruleSummary>;
  canUpload: boolean;
  canCreate: boolean;
  onPickFile: () => void;
  onUpload: () => void;
  onCreate: () => void;
  onExample: () => void;
  onShowReport: () => void;
};

function CanvasArea(props: CanvasProps) {
  const {
    file, fileId, originalFilename, task, uploading, creating, progressPct, elapsed,
    previewSrc, error, notice, summary, canUpload, canCreate,
    onPickFile, onUpload, onCreate, onExample, onShowReport,
  } = props;

  const done = task?.status === "success";
  const failed = task?.status === "failed";
  const running = task?.status === "running" || task?.status === "pending";

  return (
    <section className="flex min-w-0 flex-1 flex-col bg-ink-100">
      {/* 画布顶栏信息 */}
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-ink-150/70 bg-ink-50/80 px-5 text-[11px] text-ink-400">
        <span className="flex min-w-0 items-center gap-1.5">
          <Icon name="file" size={12} />
          <span className="truncate">{originalFilename ?? file?.name ?? "未选择文档"}</span>
        </span>
        <span>文档预览 · 画布</span>
      </div>

      {/* 提示条（错误 / 通知） */}
      {(error || notice) && (
        <div className="px-5 pt-3">
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-err-100 bg-err-100/60 px-3 py-2 text-xs text-err-600">
              <Icon name="alert" size={14} className="mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="flex items-start gap-2 rounded-md border border-ok-100 bg-ok-100/60 px-3 py-2 text-xs text-ok-600">
              <Icon name="check" size={14} className="mt-0.5" />
              <span>{notice}</span>
            </div>
          )}
        </div>
      )}

      {/* 白纸 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-12 pt-5">
        <div className="mx-auto flex min-h-[840px] w-full max-w-[820px] flex-col rounded-[4px] bg-white px-12 py-10 shadow-paper ring-1 ring-ink-150/70">
          {/* —— 空状态：未选择文档 —— */}
          {!file && (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-xl bg-ink-50 text-ink-300 ring-1 ring-ink-150">
                <Icon name="file" size={36} />
              </div>
              <p className="mt-7 text-[17px] font-semibold text-ink-950">开始新的格式化任务</p>
              <p className="mt-2.5 max-w-sm text-[13px] leading-6 text-ink-500">
                上传 .docx 文档，用自然语言描述格式需求，由智能 Agent 自动完成排版
              </p>
              <button type="button" className="btn btn-primary mt-7 h-10 px-6" onClick={onPickFile}>
                <Icon name="upload" size={15} />
                选择 .docx 文件
              </button>
              <p className="mt-4 text-[11px] text-ink-300">仅支持 .docx 格式</p>
            </div>
          )}

          {/* —— 已选文件，未上传 —— */}
          {file && !fileId && !task && (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-navy-50 text-navy-600">
                <Icon name="file" size={28} />
              </div>
              <p className="mt-5 text-[15px] font-semibold text-ink-950">{file.name}</p>
              <p className="mt-1.5 text-[13px] text-ink-400">{(file.size / 1024).toFixed(1)} KB</p>
              <div className="mt-6 flex items-center gap-3">
                <button type="button" className="btn btn-primary h-10 px-6" onClick={onUpload} disabled={!canUpload}>
                  {uploading ? "上传中…" : "上传文件"}
                </button>
                <button type="button" className="btn btn-secondary h-10 px-5" onClick={onPickFile}>
                  重新选择
                </button>
              </div>
            </div>
          )}

          {/* —— 已上传，等待创建任务 —— */}
          {file && fileId && !task && (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-ok-100 text-ok-600">
                <Icon name="check" size={28} />
              </div>
              <p className="mt-5 text-[15px] font-semibold text-ink-950">{originalFilename}</p>
              <p className="mt-1.5 font-mono text-[11px] text-ink-300">file_id: {fileId}</p>
              <p className="mt-5 max-w-sm text-[13px] leading-6 text-ink-500">
                在右侧「格式需求」中填写排版要求，或点击下方按钮直接开始
              </p>
              <div className="mt-6 flex items-center gap-3">
                <button type="button" className="btn btn-primary h-10 px-6" onClick={onCreate} disabled={!canCreate}>
                  {creating ? "创建任务中…" : "开始格式化"}
                </button>
                <button type="button" className="btn btn-secondary h-10 px-5" onClick={onExample}>
                  填入示例需求
                </button>
              </div>
            </div>
          )}

          {/* —— 任务处理中 —— */}
          {task && running && (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="relative h-16 w-16">
                <div className="absolute inset-0 rounded-full border-2 border-ink-100" />
                <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-navy-500" />
                <div className="absolute inset-0 flex items-center justify-center text-navy-600">
                  <Icon name="clock" size={20} />
                </div>
              </div>
              <p className="mt-5 text-[15px] font-medium text-ink-700">
                {task.status === "pending" ? "任务排队中…" : "正在智能格式化…"}
              </p>
              <div className="mt-5 w-full max-w-sm">
                <ProgressBar pct={progressPct} />
              </div>
              <p className="mt-2.5 text-xs text-ink-400">
                进度 {progressPct}% · 已用时 {elapsed} 秒
                {task.estimated_seconds ? ` / 预计 ${task.estimated_seconds} 秒` : ""}
              </p>
            </div>
          )}

          {/* —— 处理失败 —— */}
          {task && failed && (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-err-100 text-err-600">
                <Icon name="alert" size={26} />
              </div>
              <p className="mt-4 text-[15px] font-medium text-ink-800">格式化失败</p>
              {task.error && (
                <p className="mt-2 max-w-md rounded-md bg-err-100/60 px-3 py-2 text-xs text-err-600">
                  {task.error}
                </p>
              )}
            </div>
          )}

          {/* —— 处理成功：白纸预览 —— */}
          {task && done && (
            <div className="flex flex-1 flex-col">
              {previewSrc ? (
                <img
                  src={previewSrc}
                  alt="格式化预览"
                  className="mx-auto max-h-[900px] w-auto max-w-full rounded-[2px] shadow-soft"
                />
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center text-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-ink-100 border-t-navy-500" />
                  <p className="mt-4 text-[13px] text-ink-400">预览生成中…</p>
                </div>
              )}

              {/* 纸张页脚水印 */}
              <div className="mt-8 border-t border-ink-100 pt-4">
                <div className="flex items-center justify-between text-[11px] text-ink-300">
                  <span>{originalFilename ?? "document"}</span>
                  <span>Word 格式 Agent · 格式化预览</span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-400">
                  {summary.hasRules && (
                    <>
                      <span>字体 {summary.font}</span>
                      <span>字号 {summary.size}</span>
                      <span>行距 {summary.spacing}</span>
                      <span>缩进 {summary.indent}</span>
                      <span>对齐 {summary.align}</span>
                    </>
                  )}
                  {task.completed_at && task.started_at && (
                    <span className="ml-auto flex items-center gap-1">
                      <Icon name="clock" size={11} />
                      实际耗时 {formatDuration(task.started_at, task.completed_at)}
                    </span>
                  )}
                  <button type="button" className="text-navy-600 underline-offset-2 hover:underline" onClick={onShowReport}>
                    查看修改报告
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/* ============================================================
 * 右侧属性面板（字体样式 / 段落设置 / 格式需求，可折叠、可拖拽宽度）
 * ============================================================ */

type PanelProps = {
  collapsed: boolean;
  width: number;
  dragging: boolean;
  requirements: string;
  setRequirements: (v: string) => void;
  example: string;
  task: Task | null;
  creating: boolean;
  canCreate: boolean;
  progressPct: number;
  elapsed: number;
  status: Task["status"] | null;
  summary: ReturnType<typeof ruleSummary>;
  onStartResize: (e: ReactPointerEvent) => void;
  onCreate: () => void;
};

function RightPanel(props: PanelProps) {
  const {
    collapsed, width, dragging, requirements, setRequirements, example, task,
    creating, canCreate, progressPct, elapsed, status, summary, onStartResize, onCreate,
  } = props;

  const running = task?.status === "running" || task?.status === "pending";

  return (
    <aside
      className="relative flex shrink-0 flex-col overflow-hidden border-l border-ink-150 bg-ink-50/60"
      style={{
        width: collapsed ? 0 : width,
        minWidth: 0,
        transition: dragging ? "none" : "width 300ms ease",
      }}
    >
      {/* 拖拽调宽手柄（左边缘） */}
      {!collapsed && (
        <div
          onPointerDown={onStartResize}
          className="absolute inset-y-0 left-0 z-10 w-1.5 cursor-col-resize bg-transparent transition-colors duration-300 hover:bg-navy-200/60"
          title="拖拽调整宽度"
        />
      )}

      <div className="min-w-[300px] flex-1 space-y-5 overflow-y-auto px-4 py-5">
        {/* —— 格式需求 —— */}
        <section>
          <CardTitle>格式需求</CardTitle>
          <div className="panel mt-3 p-4">
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder={example}
              rows={5}
              className="input resize-none"
            />
            <div className="mt-4 flex items-center justify-between">
              <button type="button" className="text-[11px] text-navy-600 underline-offset-2 hover:underline" onClick={() => setRequirements(example)}>
                填入示例需求
              </button>
              <button
                type="button"
                className="btn btn-primary h-8 px-4 text-xs"
                onClick={onCreate}
                disabled={!canCreate}
              >
                {creating ? "处理中…" : "开始格式化"}
              </button>
            </div>
          </div>
        </section>

        {/* —— 字体样式 —— */}
        <section>
          <CardTitle>字体样式</CardTitle>
          <div className="panel mt-3 px-4 py-3">
            <InfoRow label="中文字体" value={summary.font} active={summary.hasRules} />
            <InfoRow label="字号" value={summary.size} active={summary.hasRules} />
            <InfoRow label="标题层级" value={task?.format_rules ? `${(task.format_rules.headings as unknown[] | undefined)?.length ?? 0} 级` : "—"} active={summary.hasRules} />
            {!summary.hasRules && (
              <p className="pt-2 text-[11px] text-ink-300">创建任务并生成规则后显示</p>
            )}
          </div>
        </section>

        {/* —— 段落 —— */}
        <section>
          <CardTitle>段落</CardTitle>
          <div className="panel mt-3 px-4 py-3">
            <InfoRow label="行距" value={summary.spacing} active={summary.hasRules} />
            <InfoRow label="首行缩进" value={summary.indent} active={summary.hasRules} />
            <InfoRow label="对齐方式" value={summary.align} active={summary.hasRules} />
          </div>
        </section>

        {/* —— 处理状态 —— */}
        {task && (
          <section>
            <CardTitle>处理状态</CardTitle>
            <div className="panel mt-3 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-ink-500">任务状态</span>
                <StatusBadge status={task.status} />
              </div>
              {running && (
                <div className="mt-3">
                  <ProgressBar pct={progressPct} />
                  <p className="mt-2 text-[11px] text-ink-400">
                    进度 {progressPct}% · 已用时 {elapsed} 秒
                  </p>
                </div>
              )}
              {task.status === "success" && task.completed_at && task.started_at && (
                <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-ink-400">
                  <Icon name="clock" size={12} />
                  实际耗时 {formatDuration(task.started_at, task.completed_at)}
                </p>
              )}
              {task.status === "failed" && task.error && (
                <p className="mt-2.5 text-[11px] text-err-600">{task.error}</p>
              )}
              <p className="mt-3 flex items-center gap-1.5 border-t border-ink-100 pt-3 text-[11px] text-ink-300">
                <Icon name="shield" size={12} />
                会话隔离 · 数据仅对当前设备可见
              </p>
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}

/* ============================================================
 * 主页面（全部业务逻辑原样保留）
 * ============================================================ */

export default function Home() {
  /* —— 业务状态（原样保留） —— */
  const [file, setFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [originalFilename, setOriginalFilename] = useState<string | null>(null);
  const [requirements, setRequirements] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* —— 新增纯 UI 状态 —— */
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(252);
  const [panelWidth, setPanelWidth] = useState(316);
  const [dragging, setDragging] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => { return () => { stopPolling(); if (elapsedRef.current) clearInterval(elapsedRef.current); }; }, [stopPolling]);

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      if (elapsedRef.current) clearInterval(elapsedRef.current);
      setElapsed(0);
      elapsedRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      const poll = async () => {
        try {
          const t = await getTask(id);
          setTask(t);
          if (t.status === "success" || t.status === "failed") {
            stopPolling();
            if (elapsedRef.current) { clearInterval(elapsedRef.current); elapsedRef.current = null; }
            if (t.status === "success") {
              try {
                const url = await fetchPreviewBlobUrl(t.id, "png");
                setPreviewSrc(url);
              } catch {
                // 预览可能尚未生成
              }
            }
          }
        } catch (err) {
          setError((err as Error).message);
          stopPolling();
        }
      };
      void poll();
      timerRef.current = setInterval(() => void poll(), 2000);
    },
    [stopPolling],
  );

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setFileId(null);
    setOriginalFilename(null);
    setTaskId(null);
    setTask(null);
    setError(null);
    setNotice(null);
    setPreviewSrc(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      const r = await uploadFile(file);
      setFileId(r.file_id);
      setOriginalFilename(r.original_filename);
      setNotice(`上传成功：${r.original_filename}（${(r.size / 1024).toFixed(1)} KB）`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const handleCreate = async () => {
    if (!fileId) return;
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const r = await createTask(fileId, requirements, originalFilename ?? "");
      setTaskId(r.task_id);
      setTask(null);
      setPreviewSrc(null);
      startPolling(r.task_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const handleUndo = async () => {
    if (!taskId) return;
    setUndoing(true);
    setError(null);
    setNotice(null);
    try {
      const r = await undoTask(taskId);
      setNotice(r.message ?? "已撤销");
      const t = await getTask(taskId);
      setTask(t);
      try {
        const url = await fetchPreviewBlobUrl(taskId, "png");
        setPreviewSrc(url);
      } catch {
        // 预览可能尚未生成
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUndoing(false);
    }
  };

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      await downloadFile(taskId, task?.original_filename ?? "");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handlePreviewPdf = async () => {
    if (!taskId) return;
    try {
      const url = await fetchPreviewBlobUrl(taskId, "pdf");
      window.open(url, "_blank");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const progressPct = Math.round((task?.progress ?? 0) * 100);
  const done = task?.status === "success";

  /* —— 纯 UI 行为：面板宽度拖拽 —— */
  const startResize = (e: ReactPointerEvent, which: "left" | "right") => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = which === "left" ? sidebarWidth : panelWidth;
    const onMove = (ev: globalThis.PointerEvent) => {
      const dx = ev.clientX - startX;
      if (which === "left") setSidebarWidth(clamp(startW + dx, 200, 400));
      else setPanelWidth(clamp(startW - dx, 300, 480));
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    setDragging(true);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const openFilePicker = () => fileInputRef.current?.click();
  const summary = ruleSummary(task);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ink-50">
      {/* 顶部工具栏 */}
      <TopBar
        status={task?.status ?? null}
        done={done}
        uploading={uploading}
        creating={creating}
        undoing={undoing}
        hasFile={!!file}
        hasFileId={!!fileId}
        canUndo={done && !undoing}
        canDownload={done}
        hasReport={!!task?.report}
        summary={summary}
        sidebarCollapsed={sidebarCollapsed}
        panelCollapsed={panelCollapsed}
        onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
        onTogglePanel={() => setPanelCollapsed((c) => !c)}
        onPickFile={openFilePicker}
        onCreate={handleCreate}
        onUndo={handleUndo}
        onDownload={handleDownload}
        onPreviewPdf={handlePreviewPdf}
        onExample={() => setRequirements(EXAMPLE_REQUIREMENT)}
        onShowReport={() => setShowReport(true)}
      />

      {/* 主体三栏 */}
      <div className="flex min-h-0 flex-1">
        <LeftSidebar
          collapsed={sidebarCollapsed}
          width={sidebarWidth}
          dragging={dragging}
          file={file}
          fileId={fileId}
          originalFilename={originalFilename}
          task={task}
          uploading={uploading}
          canUpload={!!file && !fileId && !uploading}
          onStartResize={(e) => startResize(e, "left")}
          onPickFile={openFilePicker}
          onUpload={handleUpload}
        />

        <CanvasArea
          file={file}
          fileId={fileId}
          originalFilename={originalFilename}
          task={task}
          uploading={uploading}
          creating={creating}
          progressPct={progressPct}
          elapsed={elapsed}
          previewSrc={previewSrc}
          error={error}
          notice={notice}
          summary={summary}
          canUpload={!!file && !fileId && !uploading}
          canCreate={!!fileId && !creating}
          onPickFile={openFilePicker}
          onUpload={handleUpload}
          onCreate={handleCreate}
          onExample={() => setRequirements(EXAMPLE_REQUIREMENT)}
          onShowReport={() => setShowReport(true)}
        />

        <RightPanel
          collapsed={panelCollapsed}
          width={panelWidth}
          dragging={dragging}
          requirements={requirements}
          setRequirements={setRequirements}
          example={EXAMPLE_REQUIREMENT}
          task={task}
          creating={creating}
          canCreate={!!fileId && !creating}
          progressPct={progressPct}
          elapsed={elapsed}
          status={task?.status ?? null}
          summary={summary}
          onStartResize={(e) => startResize(e, "right")}
          onCreate={handleCreate}
        />
      </div>

      {/* 隐藏的文件输入（业务逻辑不变，仅改为受控触发） */}
      <input ref={fileInputRef} type="file" accept=".docx" className="hidden" onChange={handleFileChange} />

      {/* 修改报告弹窗 */}
      {showReport && task && (
        <Modal title="修改报告" onClose={() => setShowReport(false)}>
          <ReportPanel task={task} />
        </Modal>
      )}
    </div>
  );
}
