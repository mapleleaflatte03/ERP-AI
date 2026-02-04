import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Bot,
  MessageSquare,
  Send,
  X,
  Minus,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import api from '../../lib/api';
import ActionProposalCard from '../ActionProposalCard';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  action_proposals?: Array<{
    action_id: string;
    action_type: string;
    description: string;
    status: 'proposed' | 'executed' | 'cancelled' | 'failed';
    requires_confirmation: boolean;
  }>;
}

interface ModuleChatDockProps {
  module: string;
  scope?: Record<string, string | number | null | undefined>;
}

type ModulePanelState = {
  open: boolean;
  minimized: boolean;
  expanded: boolean;
  width: number;
  height: number;
  x: number;
  y: number;
  session_id?: string;
};

type ChatState = {
  version: number;
  modules: Record<string, ModulePanelState>;
};

const STORAGE_KEY = 'erpx_chat_state';

const DEFAULT_SIZE = {
  width: 380,
  height: 520,
};

const getDefaultPanel = (): ModulePanelState => {
  const safeWindow = typeof window !== 'undefined'
    ? { w: window.innerWidth, h: window.innerHeight }
    : { w: 1200, h: 800 };
  const x = Math.max(24, safeWindow.w - DEFAULT_SIZE.width - 24);
  const y = Math.max(24, safeWindow.h - DEFAULT_SIZE.height - 24);
  return {
    open: true,
    minimized: false,
    expanded: false,
    width: DEFAULT_SIZE.width,
    height: DEFAULT_SIZE.height,
    x,
    y,
  };
};

const loadChatState = (): ChatState => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { version: 1, modules: {} };
    }
    const parsed = JSON.parse(raw) as ChatState;
    if (!parsed || typeof parsed !== 'object') {
      return { version: 1, modules: {} };
    }
    return {
      version: parsed.version || 1,
      modules: parsed.modules || {},
    };
  } catch {
    return { version: 1, modules: {} };
  }
};

const persistModuleState = (moduleKey: string, state: ModulePanelState) => {
  try {
    const current = loadChatState();
    const next: ChatState = {
      version: current.version || 1,
      modules: {
        ...current.modules,
        [moduleKey]: state,
      },
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore storage errors
  }
};

const buildGreeting = (moduleKey: string) => {
  switch (moduleKey) {
    case 'documents':
      return 'Chào bạn! Tôi có thể tóm tắt chứng từ, trích xuất dữ liệu và gợi ý kiểm tra.';
    case 'proposals':
      return 'Chào bạn! Tôi hỗ trợ kiểm tra đề xuất hạch toán và đề xuất phê duyệt.';
    case 'approvals':
      return 'Chào bạn! Tôi hỗ trợ rà soát chứng từ chờ duyệt và đề xuất hành động.';
    case 'analyze':
      return 'Chào bạn! Tôi có thể giải thích báo cáo và hỗ trợ phân tích dữ liệu (read-only).';
    default:
      return 'Chào bạn! Tôi sẵn sàng hỗ trợ.';
  }
};

export default function ModuleChatDock({ module, scope }: ModuleChatDockProps) {
  const moduleKey = module.toLowerCase();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; startLeft: number; startTop: number } | null>(null);
  const prevBoxRef = useRef<{ width: number; height: number; x: number; y: number } | null>(null);

  const initialPanel = useMemo(() => {
    const loaded = loadChatState();
    const base = getDefaultPanel();
    const existing = loaded.modules[moduleKey];
    return {
      ...base,
      ...existing,
    } as ModulePanelState;
  }, [moduleKey]);

  const [open, setOpen] = useState(initialPanel.open);
  const [minimized, setMinimized] = useState(initialPanel.minimized);
  const [expanded, setExpanded] = useState(initialPanel.expanded);
  const [width, setWidth] = useState(initialPanel.width);
  const [height, setHeight] = useState(initialPanel.height);
  const [x, setX] = useState(initialPanel.x);
  const [y, setY] = useState(initialPanel.y);
  const [sessionId] = useState(() => {
    const existing = initialPanel.session_id;
    const next = existing || (typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${moduleKey}-${Date.now()}`);
    return next;
  });

  useEffect(() => {
    persistModuleState(moduleKey, {
      open,
      minimized,
      expanded,
      width,
      height,
      x,
      y,
      session_id: sessionId,
    });
  }, [moduleKey, open, minimized, expanded, width, height, x, y, sessionId]);

  useEffect(() => {
    if (!panelRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const box = entry.contentRect;
        if (!expanded) {
          setWidth(Math.round(box.width));
          setHeight(Math.round(box.height));
        }
      }
    });
    observer.observe(panelRef.current);
    return () => observer.disconnect();
  }, [expanded]);

  useEffect(() => {
    const onResize = () => {
      if (expanded) return;
      const safeW = window.innerWidth;
      const safeH = window.innerHeight;
      setX((prev) => Math.min(Math.max(16, prev), Math.max(16, safeW - width - 16)));
      setY((prev) => Math.min(Math.max(16, prev), Math.max(16, safeH - height - 16)));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [expanded, width, height]);

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: buildGreeting(moduleKey),
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');

  const chatMutation = useMutation({
    mutationFn: (variables: { message: string; context: Record<string, any> }) =>
      api.sendCopilotMessage(variables.message, variables.context),
    onSuccess: (response) => {
      const assistantMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.response || response.content || 'Xin lỗi, tôi không thể xử lý yêu cầu này.',
        action_proposals: response.action_proposals || (
          response.tool_results?.filter((r: any) => r.requires_confirmation).map((r: any) => ({
            action_id: r.action_id,
            action_type: r.action_type,
            description: r.description,
            status: r.status || 'proposed',
            requires_confirmation: true,
          }))
        ),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    },
    onError: () => {
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Không thể kết nối đến dịch vụ AI. Vui lòng thử lại.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    },
  });

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return;
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    chatMutation.mutate({
      message: input.trim(),
      context: {
        module: moduleKey,
        session_id: sessionId,
        scope: scope || {},
      },
    });
  };

  const handleHeaderMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (expanded) return;
    const target = event.target as HTMLElement;
    if (target.closest('button')) return;
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startLeft: x,
      startTop: y,
    };
    event.preventDefault();
  };

  useEffect(() => {
    const handleMove = (event: MouseEvent) => {
      if (!dragRef.current) return;
      const dx = event.clientX - dragRef.current.startX;
      const dy = event.clientY - dragRef.current.startY;
      const nextX = dragRef.current.startLeft + dx;
      const nextY = dragRef.current.startTop + dy;
      const safeW = window.innerWidth;
      const safeH = window.innerHeight;
      setX(Math.min(Math.max(16, nextX), Math.max(16, safeW - width - 16)));
      setY(Math.min(Math.max(16, nextY), Math.max(16, safeH - height - 16)));
    };

    const handleUp = () => {
      dragRef.current = null;
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [width, height]);

  const toggleExpand = () => {
    if (!expanded) {
      prevBoxRef.current = { width, height, x, y };
      setExpanded(true);
      setMinimized(false);
      return;
    }
    const prev = prevBoxRef.current;
    if (prev) {
      setWidth(prev.width);
      setHeight(prev.height);
      setX(prev.x);
      setY(prev.y);
    }
    setExpanded(false);
  };

  const scopeLabel = useMemo(() => {
    if (!scope) return 'global';
    const scopeEntries = Object.entries(scope).filter(([, value]) => value);
    if (scopeEntries.length === 0) return 'global';
    const [key, value] = scopeEntries[0];
    if (!value) return 'global';
    const short = String(value).slice(0, 8);
    return `${key}:${short}`;
  }, [scope]);

  if (!open) {
    return (
      <button
        className="module-chat-fab"
        onClick={() => setOpen(true)}
        aria-label="Open module chat"
      >
        <MessageSquare className="w-4 h-4" />
        Chat {moduleKey}
      </button>
    );
  }

  return (
    <div
      ref={panelRef}
      className={`module-chat-dock ${expanded ? 'is-expanded' : ''} ${minimized ? 'is-minimized' : ''}`}
      style={{
        left: expanded ? '5vw' : x,
        top: expanded ? '8vh' : y,
        width: expanded ? '90vw' : width,
        height: expanded ? '80vh' : height,
        resize: expanded ? 'none' : 'both',
      }}
    >
      <div
        className="module-chat-header"
        onMouseDown={handleHeaderMouseDown}
      >
        <div className="flex items-center gap-2">
          <div className="module-chat-icon">
            <Bot className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="module-chat-title">Module Chat</div>
            <div className="module-chat-subtitle">{moduleKey} · {scopeLabel}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="module-chat-control"
            onClick={() => setMinimized((prev) => !prev)}
            aria-label="Minimize"
          >
            {minimized ? <Maximize2 className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
          </button>
          <button
            className="module-chat-control"
            onClick={toggleExpand}
            aria-label="Expand"
          >
            {expanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button
            className="module-chat-control"
            onClick={() => setOpen(false)}
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!minimized && (
        <>
          <div className="module-chat-body">
            {messages.map((msg) => (
              <div key={msg.id} className={`module-chat-message ${msg.role}`}>
                <div className="module-chat-bubble">
                  <p>{msg.content}</p>
                </div>
                {msg.action_proposals && msg.action_proposals.length > 0 && (
                  <div className="module-chat-proposals">
                    {msg.action_proposals.map((proposal) => (
                      <ActionProposalCard
                        key={proposal.action_id}
                        proposal={proposal}
                        onStatusChange={(newStatus) => {
                          setMessages((prev) => prev.map((m) =>
                            m.id === msg.id
                              ? {
                                  ...m,
                                  action_proposals: m.action_proposals?.map((p) =>
                                    p.action_id === proposal.action_id
                                      ? { ...p, status: newStatus as any }
                                      : p
                                  ),
                                }
                              : m
                          ));
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="module-chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Nhập câu hỏi..."
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || chatMutation.isPending}
              aria-label="Send"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
