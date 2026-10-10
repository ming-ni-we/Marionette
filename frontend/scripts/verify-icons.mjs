/* 校验 icons.ts 中导出的每个 Lucide 图标名真实存在于 lucide-react。
 * 用法：node scripts/verify-icons.mjs  （在 frontend/ 下）
 * 目的：图标库锁定唯一（Lucide），任何拼错/版本改名都会在 CI 前暴露。 */
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const lucide = require('lucide-react');

const src = readFileSync(new URL('../src/components/icons.ts', import.meta.url), 'utf8');
const block = src.slice(src.indexOf('export {'), src.indexOf('} from', src.indexOf('export {')));
const names = block
  .replace('export {', '')
  .split(/[,\n]/)
  .map((s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/g, '').trim())
  .filter((s) => /^[A-Z][A-Za-z0-9]*$/.test(s));

// lucide-react 1.x 的图标是 React.forwardRef 组件（对象，非 function），
// 因此按"键存在 + 是合法 React 组件"判定。
const isComponent = (v) =>
  typeof v === 'function' ||
  (v !== null && typeof v === 'object' && typeof v.$$typeof === 'symbol');

const missing = names.filter((n) => !isComponent(lucide[n]));

console.log(`检查图标名：${names.length} 个`);
if (missing.length) {
  console.log(`缺失 ${missing.length} 个：`);
  for (const m of missing) console.log(`  - ${m}`);
  process.exit(1);
}
console.log('全部存在 ✓');
