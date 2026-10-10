import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'dark' | 'light';
export type Density = 'studio' | 'session';

/** 会话阅读偏好（存本机，无需账号）——对标 RisuAI 的显示设置 */
export interface ReadingPrefs {
  /** 叙事正文字号档：base(15px) / lg(16px) / xl(18px) */
  fontSize: 'base' | 'lg' | 'xl';
  /** 阅读列宽（ch） */
  measure: number;
}

interface UiState {
  theme: Theme;
  density: Density;
  /** 左 rail 文字标签展开 */
  railExpanded: boolean;
  /** 工作台右侧"快速开始"面板 */
  quickStartOpen: boolean;
  /** 会话运行时：上下文/分支抽屉 */
  sessionDrawer: 'none' | 'context' | 'tree';
  /** 会话运行时：沉浸模式（隐藏所有 chrome） */
  immersive: boolean;
  reading: ReadingPrefs;

  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setDensity: (density: Density) => void;
  toggleRail: () => void;
  setQuickStartOpen: (open: boolean) => void;
  setSessionDrawer: (drawer: UiState['sessionDrawer']) => void;
  setImmersive: (immersive: boolean) => void;
  setReading: (patch: Partial<ReadingPrefs>) => void;
}

const FONT_SIZE_MAP: Record<ReadingPrefs['fontSize'], string> = {
  base: 'var(--text-md)',
  lg: 'var(--text-lg)',
  xl: 'var(--text-xl)',
};

export function applyReadingPrefs(prefs: ReadingPrefs): void {
  if (typeof document === 'undefined') return;
  document.documentElement.style.setProperty('--reading-font-size', FONT_SIZE_MAP[prefs.fontSize]);
  document.documentElement.style.setProperty('--reading-measure', `${prefs.measure}ch`);
}

function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
}

function applyDensity(density: Density): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-density', density);
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      density: 'studio',
      railExpanded: true,
      quickStartOpen: true,
      sessionDrawer: 'none',
      immersive: false,
      reading: { fontSize: 'lg', measure: 68 },

      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      toggleTheme: () => {
        const theme: Theme = get().theme === 'dark' ? 'light' : 'dark';
        applyTheme(theme);
        set({ theme });
      },
      setDensity: (density) => {
        applyDensity(density);
        set({ density });
      },
      toggleRail: () => set((s) => ({ railExpanded: !s.railExpanded })),
      setQuickStartOpen: (quickStartOpen) => set({ quickStartOpen }),
      setSessionDrawer: (sessionDrawer) => set({ sessionDrawer }),
      setImmersive: (immersive) => set({ immersive }),
      setReading: (patch) => {
        const reading = { ...get().reading, ...patch };
        applyReadingPrefs(reading);
        set({ reading });
      },
    }),
    {
      name: 'marionette.ui',
      partialize: (s) => ({
        theme: s.theme,
        density: s.density,
        railExpanded: s.railExpanded,
        quickStartOpen: s.quickStartOpen,
        reading: s.reading,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          applyTheme(state.theme);
          applyDensity(state.density);
          applyReadingPrefs(state.reading);
        }
      },
    },
  ),
);

/** 应用启动时调用一次，把持久化的偏好同步到 <html> */
export function bootstrapUiPreferences(): void {
  const { theme, density, reading } = useUiStore.getState();
  applyTheme(theme);
  applyDensity(density);
  applyReadingPrefs(reading);
}

/* ------------------------------------------------------------------ Toast */

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: 'default' | 'success' | 'warn' | 'danger';
}

interface ToastState {
  toasts: ToastItem[];
  push: (toast: Omit<ToastItem, 'id'>) => string;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = `t-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = {
  show: (title: string, description?: string) =>
    useToastStore.getState().push({ title, description, variant: 'default' }),
  success: (title: string, description?: string) =>
    useToastStore.getState().push({ title, description, variant: 'success' }),
  warn: (title: string, description?: string) =>
    useToastStore.getState().push({ title, description, variant: 'warn' }),
  danger: (title: string, description?: string) =>
    useToastStore.getState().push({ title, description, variant: 'danger' }),
};
