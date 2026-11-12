import { useCallback, useEffect, useRef, useState } from "react";
import {
  appendHomeMessage,
  homeThreadKey,
  loadHomeMessages,
  markHomeMessageConfirmed,
  saveHomeMessages,
  type HomeConversationMessage,
} from "./conversation";

interface ThreadState {
  key: string;
  messages: HomeConversationMessage[];
  hydrated: boolean;
}

/**
 * 今日对话本地历史：按用户 + 竞彩日隔离，返回/重启后恢复。
 * 消息只存展示所需字段，不等同于服务端审计或账本。
 */
export function useHomeConversation(date: string, userId: string) {
  const key = homeThreadKey(userId, date);
  const [state, setState] = useState<ThreadState>({
    key,
    messages: [],
    hydrated: false,
  });
  const pending = useRef<HomeConversationMessage[]>([]);

  useEffect(() => {
    let alive = true;
    pending.current = [];
    setState({ key, messages: [], hydrated: false });
    void loadHomeMessages(key).then((stored) => {
      if (!alive) return;
      const queued = pending.current;
      pending.current = [];
      const merged = queued.reduce(appendHomeMessage, stored);
      setState({ key, messages: merged, hydrated: true });
    });
    return () => {
      alive = false;
    };
  }, [key]);

  useEffect(() => {
    if (!state.hydrated || state.key !== key) return;
    void saveHomeMessages(key, state.messages);
  }, [key, state]);

  const append = useCallback((message: HomeConversationMessage) => {
    setState((prev) => {
      if (!prev.hydrated) {
        pending.current = appendHomeMessage(pending.current, message);
        return prev;
      }
      return { ...prev, messages: appendHomeMessage(prev.messages, message) };
    });
  }, []);

  const confirm = useCallback((messageId: string) => {
    setState((prev) => ({
      ...prev,
      messages: markHomeMessageConfirmed(prev.messages, messageId),
    }));
  }, []);

  return {
    messages: state.messages,
    hydrated: state.hydrated,
    append,
    confirm,
  };
}
