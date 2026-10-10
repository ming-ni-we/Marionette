import { PageHeader } from '@/components/common/page-header';
import { AccessSection } from '@/components/settings/access-section';
import { LlmSection } from '@/components/settings/llm-section';
import { ModerationSection } from '@/components/settings/moderation-section';
import { ImageBackendSection } from '@/components/settings/image-backend-section';
import { DiagnosticsSection } from '@/components/settings/diagnostics-section';

/** 设置页（SPEC §7）：访问口令 · 模型后端 · 审核层 · 出图后端 · 诊断包导出 */
export function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl pb-20">
      <PageHeader
        title="设置"
        description="这台实例的接入配置：访问口令、模型后端、内容审核层、出图后端，以及一键导出诊断包。所有改动即时生效，不用重启容器。"
      />
      <div className="space-y-6 px-6 py-6">
        <AccessSection />
        <LlmSection />
        <ModerationSection />
        <ImageBackendSection />
        <DiagnosticsSection />
      </div>
    </div>
  );
}
