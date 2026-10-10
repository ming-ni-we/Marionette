import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from '@/stores/ui';
import { Button } from '@/components/ui/button';
import { SettingsSection } from './section';
import { FileDown, ExternalLink, Database } from '@/components/icons';

/** 诊断与数据：导出诊断包（F10）+ 回到首启向导 */
export function DiagnosticsSection() {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('/api/v1/diagnostics/export', { credentials: 'include' });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `marionette-diagnostics-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success('诊断包已开始下载', '内容为本地日志 + 自检结果 + 配置快照（已脱敏）。');
    } catch {
      toast.danger('导出失败', '未能从后端取到诊断包，确认实例在线后重试。');
    } finally {
      setExporting(false);
    }
  };

  return (
    <SettingsSection
      icon={FileDown}
      title="诊断与数据"
      aside={<span className="text-sm text-meta">本地落盘 · 不上报云端</span>}
    >
      <p className="text-base leading-relaxed text-muted">
        排查问题时导出诊断包：本地日志、环境自检结果、配置快照打包成一个 zip。密钥与原始对话内容不包含在内。
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={handleExport} loading={exporting}>
          <FileDown className="size-4" aria-hidden="true" />
          导出诊断包（zip）
        </Button>
        <Button variant="ghost" asChild>
          <a href="/api/v1/system/selfcheck" target="_blank" rel="noreferrer">
            <ExternalLink className="size-4" aria-hidden="true" />
            查看原始自检 JSON
          </a>
        </Button>
      </div>

      <div className="border-t border-border-soft pt-4">
        <p className="text-sm leading-relaxed text-muted">
          需要重新走一遍首启流程（换模型后端 / 重装示例内容）？回到
          <Link to="/setup" className="mx-1 text-accent underline-offset-2 hover:underline">
            首启向导
          </Link>
          即可。数据库连接与端口信息在
          <span className="mx-1 inline-flex items-center gap-1 text-fg-2">
            <Database className="size-3.5" aria-hidden="true" />
            <code className="font-mono text-sm">.env</code>
          </span>
          中维护。
        </p>
      </div>
    </SettingsSection>
  );
}
