/**
 * 图标注册表 —— 全项目唯一图标出口（P0 铁律）
 * -----------------------------------------------------------------------------
 * 规范（docs/03-uiux.md §6 / SPEC §8）：
 *   - 唯一图标库：Lucide（lucide-react），禁止引入第二套，禁止 emoji 作功能图标
 *   - 统一描边型 SVG，stroke-width: 2，24×24 网格
 *   - 尺寸仅 16 / 20 / 24px 三档（ICON_SIZE.inline | button | standalone）
 *   - 颜色一律 currentColor 继承，禁止硬编码色值
 *   - 语义图标配 aria-label；纯图标按钮必须有 aria-label；装饰性图标 aria-hidden
 *
 * 用法：import { Search, Plus } from '@/components/icons';
 *      <Search className="size-4" aria-hidden="true" />
 * -----------------------------------------------------------------------------
 */
export {
  /* 新建 / 添加 */
  Plus,
  CirclePlus,
  UserRoundPlus,
  BookPlus,
  SlidersHorizontal,
  MessagesSquare,
  MessageSquare,
  /* 导入 / 导出 / 迁移 */
  Download,
  Upload,
  FileDown,
  FileUp,
  Copy,
  Trash2,
  Pencil,
  Save,
  Undo2,
  Redo2,
  /* 检索 / 组织 */
  Search,
  Filter,
  ArrowUpDown,
  Tags,
  Star,
  Archive,
  Folder,
  /* 图集 / 图像 */
  Images,
  ImagePlus,
  Image,
  Sparkles,
  Crop,
  /* 内容实体 */
  BookOpen,
  BookMarked,
  ListTree,
  KeyRound,
  Brain,
  UserRound,
  UserCog,
  UsersRound,
  /* 分支 / 时间 */
  GitBranch,
  GitFork,
  Network,
  History,
  Clock,
  /* 参数 / 引擎 */
  ToggleRight,
  ToggleLeft,
  Weight,
  Layers,
  Terminal,
  Coins,
  Hash,
  Gauge,
  /* 结构 / 导航 */
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronsDown,
  GripVertical,
  Columns2,
  PanelRight,
  PanelLeft,
  PanelRightOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Maximize2,
  Minimize2,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  CornerUpLeft,
  Ellipsis,
  Compass,
  /* 会话运行时 */
  Send,
  Square,
  Pause,
  RefreshCw,
  ArrowLeftRight,
  Type,
  Volume2,
  LoaderCircle,
  /* 系统 */
  Settings,
  Sun,
  Moon,
  Keyboard,
  CircleHelp,
  MessageSquareWarning,
  X,
  Minus,
  Check,
  Info,
  TriangleAlert,
  CircleAlert,
  CircleX,
  CircleCheck,
  Eye,
  EyeOff,
  Lock,
  LogOut,
  Power,
  Plug,
  Database,
  Cloud,
  HardDrive,
  Cpu,
  ShieldCheck,
  Sparkle,
  Palette,
  Wrench,
} from 'lucide-react';

/**
 * 尺寸档位（仅三档，见 --icon-size-inline|button|standalone）
 * 使用 Tailwind size-* 工具类，保证 16 / 20 / 24px 不越界。
 */
export const ICON_SIZE = {
  /** 16px — 行内图标（w-4 h-4） */
  inline: 'size-4',
  /** 20px — 按钮内图标（w-5 h-5） */
  button: 'size-5',
  /** 24px — 独立图标（w-6 h-6） */
  standalone: 'size-6',
} as const;

export type IconSizeKey = keyof typeof ICON_SIZE;

/**
 * 图标组件类型别名。
 * 不直接依赖 lucide-react 的导出类型名，便于在 props 层统一约束。
 */
export type IconComponent = import('react').ComponentType<{
  className?: string;
  'aria-hidden'?: boolean | 'true' | 'false';
  'aria-label'?: string;
  strokeWidth?: number | string;
}>;
