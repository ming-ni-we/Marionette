import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/common/page-header';
import { Button } from '@/components/ui/button';
import { StepIndicator } from '@/components/setup/step-indicator';
import { SelfCheckStep } from '@/components/setup/selfcheck-step';
import { LlmStep } from '@/components/setup/llm-step';
import { SamplesStep } from '@/components/setup/samples-step';
import { ArrowRight } from '@/components/icons';

/** 首启向导（SPEC §7）：环境自检 → 接入模型 → 安装示例内容 */
export function SetupPage() {
  const [step, setStep] = useState(1);

  return (
    <div className="mx-auto w-full max-w-3xl pb-16">
      <PageHeader
        title="首启向导"
        description="三步：确认环境可用 → 接一个模型后端 → 装示例内容。全程约 3 分钟，不用改配置文件。"
        actions={
          <Button variant="ghost" asChild>
            <Link to="/">
              先跳过，去内容库
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        }
      />

      <StepIndicator step={step} onSelect={setStep} />

      <div className="px-6">
        {step === 1 ? <SelfCheckStep onNext={() => setStep(2)} /> : null}
        {step === 2 ? <LlmStep onBack={() => setStep(1)} onSaved={() => setStep(3)} /> : null}
        {step === 3 ? <SamplesStep onBack={() => setStep(2)} /> : null}
      </div>
    </div>
  );
}
