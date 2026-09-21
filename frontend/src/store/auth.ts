import { create } from "zustand";
import {
  api,
  clearTokens,
  getToken,
  sessionToken,
  setTokens,
  type User,
} from "../api";

interface AuthState {
  user: User | null;
  loading: boolean;
  init: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  ssoCallback: () => Promise<void>;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  init: async () => {
    if (!getToken()) {
      set({ loading: false, user: null });
      return;
    }
    try {
      const user = await api.me();
      set({ user, loading: false });
    } catch {
      clearTokens();
      set({ user: null, loading: false });
    }
  },
  login: async (email, password) => {
    const res = await api.login(email, password);
    setTokens(res.access, res.refresh);
    set({ user: res.user });
  },
  register: async (email, name, password) => {
    await api.register(email, name, password);
    await useAuth.getState().login(email, password);
  },
  ssoCallback: async () => {
    const res = await sessionToken();
    setTokens(res.access, res.refresh);
    set({ user: res.user });
  },
  logout: () => {
    clearTokens();
    set({ user: null });
  },
}));
