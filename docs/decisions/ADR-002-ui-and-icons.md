# ADR-002: UI 组件库采用 shadcn/ui + Tailwind CSS，图标库锁定 Lucide

## Status
Accepted (2026-10-09)

## Background
需要一套**可深度定制、无运行时黑盒**、且能与自定义设计 token 体系契合的组件库。团队级 P0 规则要求：**锁定唯一一套 SVG 图标库**（统一描边、可矢量缩放、16/20/24px 尺寸），**禁止 emoji 作为功能图标**，**禁止紫色→粉色渐变**，**禁止硬编码颜色**。
候选组件库：shadcn/ui (Radix)、Ant Design 5、MUI 6/7。
候选图标库：Lucide、Heroicons、Tabler、Phosphor。

## Decision
1. 组件库选 **shadcn/ui（Radix UI primitives + Tailwind CSS 4.1）**：源码复制入仓、可按需改造、无障碍由 Radix 保障、与 Tailwind token 体系天然契合。
2. 图标库**锁定 `lucide-react` 1.0+**（唯一，全项目不混用）：
   - 统一 24x24 网格、默认 2px 描边、纯描边风格，满足"统一描边"要求；
   - MIT/ISC 许可、tree-shaking 良好（45 图标约 12KB gzip）；
   - 与 shadcn/ui 默认集成；
   - 尺寸规范只允许 16/20/24px；颜色继承 `currentColor`（不硬编码，唯一例外 `#fff`/`#000`）；
   - 装饰性图标 `aria-hidden`，语义图标 `role="img"` + `aria-label`。
3. 否决 Ant Design / MUI（视觉定制与 Tailwind 共存成本高）、Heroicons（图标仅 300+ 覆盖不足）、Tabler/Phosphor（既然选 Lucide 即须唯一，避免混用）。
4. Lucide 1.0 已移除品牌图标；若确需品牌标识，单独以 Simple Icons 单文件 SVG 引入（品牌资产，不构成混用图标库）。

## Consequences
- 正面：视觉一致、可定制到底、无障碍合规、包体可控；满足 P0 图标规则。
- 负面：组件需自行维护（复制入仓）；需建立内部图标使用规范文档并 lint 约束（禁止引入第二套图标包）。
- 约束：设计 token（颜色/间距/字体）由设计师定义，架构层不硬编码颜色。

## Related ADRs
- ADR-001（前端框架）
