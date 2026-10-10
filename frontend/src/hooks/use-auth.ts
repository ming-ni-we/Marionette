import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi, type AuthSession } from '@/api/client';

/** 会话校验：判断是否需要跳登录页（AC-02/03 的前端对应面） */
export function useAuthSession() {
  return useQuery<AuthSession>({
    queryKey: ['auth', 'session'],
    queryFn: authApi.session,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => authApi.login(password),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auth'] });
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      qc.clear();
    },
  });
}
