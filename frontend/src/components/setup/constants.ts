import type { ErrorClass, LlmProvider } from '@/api/types';

export const PROVIDERS: Array<{ value: LlmProvider; label: string; defaultUrl: string; hint: string }> = [
  {
    value: 'openai_compatible',
    label: 'OpenAI 兼容（通用）',
    defaultUrl: 'https://api.openai.com/v1',
    hint: '任何提供 OpenAI 兼容 /v1/chat/completions 的服务都走这一项。',
  },
  {
    value: 'deepseek',
    label: 'DeepSeek',
    defaultUrl: 'https://api.deepseek.com/v1',
    hint: '国内直连，按量计费。需要自备 API Key。',
  },
  {
    value: 'dashscope',
    label: '通义千问（DashScope）',
    defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    hint: '阿里云百炼的 OpenAI 兼容入口。',
  },
  {
    value: 'zhipu',
    label: '智谱 GLM',
    defaultUrl: 'https://open.bigmodel.cn/api/paas/v4',
    hint: '注意 GLM 的兼容端点路径以 /v4 结尾，不是 /v1。',
  },
  {
    value: 'ollama',
    label: '本机 Ollama',
    defaultUrl: 'http://host.docker.internal:11434/v1',
    hint: '容器内访问宿主机服务必须用 host.docker.internal，不能用 127.0.0.1。',
  },
];

/** 7 类错误分类 → 面向用户的中文修复指引（F1 最大流失点） */
export const ERROR_CLASS_FIX: Record<ErrorClass, string> = {
  model_not_found: '模型名不对。去服务商控制台复制准确的模型 ID——注意区分大小写与版本后缀。',
  endpoint_invalid: '端点地址不对。OpenAI 兼容端点通常必须以 /v1 结尾，检查有没有多写或少写路径。',
  auth_failed: 'API Key 无效或没填。确认没有多余空格，也没有过期。',
  quota_exhausted: '账户余额为 0 或额度已用尽。充值后再点测试。',
  network_unreachable: '连不上这个地址。若是本机 Ollama，容器内要用 host.docker.internal:11434。',
  timeout: '3 秒内没有响应。可能是网络慢或服务端冷启动，稍后重试或换更近的端点。',
  unknown: '未能归类。看下面的「服务端实际看到的模型名」再排查。',
};

export const STEPS = [
  { id: 1, title: '环境自检', desc: '确认数据库、扩展与端口都就绪' },
  { id: 2, title: '接入模型后端', desc: '填一个端点，测试连接后设为默认' },
  { id: 3, title: '安装示例内容', desc: '内置示例卡与世界书，避免空白开局' },
];
