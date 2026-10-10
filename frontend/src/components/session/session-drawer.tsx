import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Layers, GitBranch as GitBranchIcon } from '@/components/icons';
import { ContextInspection } from './context-inspection';
import { BranchTree } from './branch-tree';
import type { ContextSnapshot, Message } from '@/api/types';

interface SessionDrawerProps {
  open: boolean;
  tab: 'context' | 'tree';
  onTabChange: (tab: 'context' | 'tree') => void;
  onOpenChange: (open: boolean) => void;
  snapshot: ContextSnapshot | null;
  snapshotLoading: boolean;
  onLoadSnapshot: () => void;
  messages: Message[];
  currentMessageId?: string;
  onFork: (messageId: string) => void;
  onJump: (messageId: string) => void;
  childBranches?: Array<{ id: string; title: string }>;
}

/** 会话运行时右侧抽屉：上下文检视 / 分支树（overlay 形式，不重排阅读列） */
export function SessionDrawer({
  open,
  tab,
  onTabChange,
  onOpenChange,
  snapshot,
  snapshotLoading,
  onLoadSnapshot,
  messages,
  currentMessageId,
  onFork,
  onJump,
  childBranches,
}: SessionDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby="session-drawer-desc" className="gap-3">
        <div className="pr-6">
          <SheetTitle>引擎可见性</SheetTitle>
          <SheetDescription id="session-drawer-desc" className="mt-1">
            把"引擎到底组装了什么、为什么这样组装"摊开给你看。
          </SheetDescription>
        </div>

        <Tabs value={tab} onValueChange={(v) => onTabChange(v as 'context' | 'tree')} className="flex min-h-0 flex-1 flex-col">
          <TabsList className="shrink-0">
            <TabsTrigger value="context">
              <Layers aria-hidden="true" />
              上下文检视
            </TabsTrigger>
            <TabsTrigger value="tree">
              <GitBranchIcon aria-hidden="true" />
              分支树
            </TabsTrigger>
          </TabsList>

          <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
            <TabsContent value="context">
              <ContextInspection
                snapshot={snapshot}
                loading={snapshotLoading}
                onLoad={onLoadSnapshot}
              />
            </TabsContent>
            <TabsContent value="tree">
              <BranchTree
                messages={messages}
                currentMessageId={currentMessageId}
                onFork={onFork}
                onJump={onJump}
                childBranches={childBranches}
              />
            </TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
