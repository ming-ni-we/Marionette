import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { setUnauthorizedHandler } from '@/api/client';
import { AppLayout } from '@/components/layout/app-layout';
import { WorkspacePage } from '@/pages/workspace';
import { CardEditorPage } from '@/pages/card-editor';
import { WorldBookEditorPage } from '@/pages/worldbook-editor';
import { PresetEditorPage } from '@/pages/preset-editor';
import { SessionListPage } from '@/pages/session-list';
import { SessionRuntimePage } from '@/pages/session-runtime';
import { StoryRuntimePage } from '@/pages/story-runtime';
import { WorldsPage } from '@/pages/worlds';
import { WorldEditorPage } from '@/pages/world-editor';
import { AssetGalleryPage } from '@/pages/asset-gallery';
import { SettingsPage } from '@/pages/settings';
import { SetupPage } from '@/pages/setup';
import { LoginPage } from '@/pages/login';
import { NotFoundPage } from '@/pages/not-found';

/**
 * 路由表（SPEC §7 的 9 个页面 + /login + /setup + 404）。
 * - 创作端统一挂在 AppLayout（左 rail + 移动端 TabBar）下
 * - /login、/setup 为独立单页，不套 rail
 * - 401 由 api 层回传 → 全局跳登录（replace，避免回退到失效页）
 */
export function App() {
  const navigate = useNavigate();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      navigate('/login', { replace: true });
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate]);

  return (
    <Routes>
      {/* 独立页：不套 rail */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />

      {/* 创作端（带全局 rail） */}
      <Route element={<AppLayout />}>
        <Route index element={<WorkspacePage />} />
        <Route path="cards" element={<Navigate to="/" replace />} />
        <Route path="cards/new" element={<CardEditorPage />} />
        <Route path="cards/:cardId" element={<CardEditorPage />} />
        <Route path="worldbooks/new" element={<WorldBookEditorPage />} />
        <Route path="worldbooks/:id" element={<WorldBookEditorPage />} />
        <Route path="presets/new" element={<PresetEditorPage />} />
        <Route path="presets/:id" element={<PresetEditorPage />} />
        <Route path="sessions" element={<SessionListPage />} />
        <Route path="sessions/:id" element={<SessionRuntimePage />} />
        {/* 剧情演出（多角色 · AI 导演）：与 1v1 运行时并列，共用同一套流式状态机 */}
        <Route path="stories/:id" element={<StoryRuntimePage />} />
        {/* 剧情世界（多角色）：编辑与管理走独立工作面 */}
        <Route path="worlds" element={<WorldsPage />} />
        <Route path="worlds/new" element={<WorldEditorPage />} />
        <Route path="worlds/:worldId" element={<WorldEditorPage />} />
        <Route path="assets" element={<AssetGalleryPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
