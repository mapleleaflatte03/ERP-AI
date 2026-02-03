/**
 * ModuleChatDock - Per-module AI chat dock component
 * ==================================================
 * 
 * Features:
 * - Floating dock that can be minimized/maximized/expanded
 * - Module-scoped chat (documents, approvals, proposals, analyze)
 * - Persists state to localStorage
 * - Renders action proposals for confirmation
 * - Respects Quantum UI tokens and motion preferences
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { MessageSquare, X, Minimize2, Maximize2, Send, Loader2, ChevronDown } from 'lucide-react';
import api from '../../lib/api';
import ActionProposalCard from '../ActionProposalCard';

// Types
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  proposedActions?: ProposedAction[];
}

interface ProposedAction {
  proposal_id: string;
  action_type: string;
  description: string;
  risk_level: string;
  confirm_url: string;
}

interface ModuleChatDockProps {
  module: 'documents' | 'proposals' | 'approvals' | 'analyze';
  scopeId?: string;
  onClose?: () => void;
}

// Module-specific configuration
const MODULE_CONFIG = {
  documents: {
    title: 'Tài liệu AI',
    icon: '📄',
    placeholder: 'Hỏi về tài liệu, trích xuất, đề xuất...',
    color: 'var(--color-primary)',
  },
  proposals: {
    title: 'Đề xuất AI',
    icon: '📋',
    placeholder: 'Hỏi về đề xuất hạch toán...',
    color: '#8b5cf6',
  },
  approvals: {
    title: 'Duyệt AI',
    icon: '✅',
    placeholder: 'Hỏi về duyệt chứng từ, danh sách chờ...',
    color: '#10b981',
  },
  analyze: {
    title: 'Phân tích AI',
    icon: '📊',
    placeholder: 'Hỏi phân tích dữ liệu, báo cáo...',
    color: '#f59e0b',
  },
};

// LocalStorage keys
const STORAGE_KEY = 'erpx_chat_state';

interface ChatState {
  isOpen: boolean;
  isMinimized: boolean;
  isExpanded: boolean;
  position: { x: number; y: number };
  size: { width: number; height: number };
}

function loadChatState(module: string): ChatState {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const allStates = JSON.parse(stored);
      return allStates[module] || getDefaultState();
    }
  } catch (e) {
    console.warn('Failed to load chat state:', e);
  }
  return getDefaultState();
}

function saveChatState(module: string, state: ChatState) {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const allStates = stored ? JSON.parse(stored) : {};
    allStates[module] = state;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(allStates));
  } catch (e) {
    console.warn('Failed to save chat state:', e);
  }
}

function getDefaultState(): ChatState {
  return {
    isOpen: false,
    isMinimized: false,
    isExpanded: false,
    position: { x: 0, y: 0 },
    size: { width: 380, height: 500 },
  };
}

export default function ModuleChatDock({ module, scopeId, onClose }: ModuleChatDockProps) {
  const config = MODULE_CONFIG[module];
  const [state, setState] = useState<ChatState>(() => loadChatState(module));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `${module}-${Date.now()}`);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
  // Persist state changes
  useEffect(() => {
    saveChatState(module, state);
  }, [module, state]);
  
  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Focus input when opened
  useEffect(() => {
    if (state.isOpen && !state.isMinimized) {
      inputRef.current?.focus();
    }
  }, [state.isOpen, state.isMinimized]);
  
  const handleToggleOpen = useCallback(() => {
    setState(prev => ({ ...prev, isOpen: !prev.isOpen, isMinimized: false }));
  }, []);
  
  const handleMinimize = useCallback(() => {
    setState(prev => ({ ...prev, isMinimized: !prev.isMinimized }));
  }, []);
  
  const handleExpand = useCallback(() => {
    setState(prev => ({ ...prev, isExpanded: !prev.isExpanded }));
  }, []);
  
  const handleClose = useCallback(() => {
    setState(prev => ({ ...prev, isOpen: false }));
    onClose?.();
  }, [onClose]);
  
  const handleSendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Call module-specific chat endpoint
      const response = await api.post(`/v1/chat/${module}`, {
        message: userMessage.content,
        scope_id: scopeId,
        session_id: sessionId,
        context: { module },
      });
      
      const data = response.data;
      
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response || 'Tôi không hiểu yêu cầu.',
        timestamp: new Date(),
        proposedActions: data.proposed_actions || [],
      };
      
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ Lỗi: ${error.response?.data?.detail || error.message || 'Không thể kết nối'}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, module, scopeId, sessionId]);
  
  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);
  
  const handleActionConfirmed = useCallback((proposalId: string, status: string) => {
    // Update message to reflect confirmation status
    setMessages(prev => prev.map(msg => ({
      ...msg,
      proposedActions: msg.proposedActions?.map(action => 
        action.proposal_id === proposalId 
          ? { ...action, status } 
          : action
      ),
    })));
  }, []);
  
  // Dock button (always visible)
  if (!state.isOpen) {
    return (
      <button
        onClick={handleToggleOpen}
        className="fixed bottom-6 right-6 z-[var(--z-chat-dock)] flex items-center gap-2 px-4 py-3 rounded-full shadow-lg transition-all hover:scale-105"
        style={{ 
          backgroundColor: config.color,
          color: 'white',
        }}
        title={`Mở ${config.title}`}
      >
        <span className="text-lg">{config.icon}</span>
        <MessageSquare className="w-5 h-5" />
      </button>
    );
  }
  
  // Minimized state
  if (state.isMinimized) {
    return (
      <div 
        className="fixed bottom-6 right-6 z-[var(--z-chat-dock)] flex items-center gap-2 px-4 py-2 rounded-full shadow-lg cursor-pointer transition-all hover:shadow-xl"
        style={{ backgroundColor: config.color, color: 'white' }}
        onClick={handleMinimize}
      >
        <span>{config.icon}</span>
        <span className="text-sm font-medium">{config.title}</span>
        <ChevronDown className="w-4 h-4 rotate-180" />
      </div>
    );
  }
  
  // Full chat panel
  const panelWidth = state.isExpanded ? 600 : state.size.width;
  const panelHeight = state.isExpanded ? 700 : state.size.height;
  
  return (
    <div
      className="fixed bottom-6 right-6 z-[var(--z-chat-dock)] flex flex-col bg-[var(--color-bg-elevated)] rounded-xl shadow-xl border border-[var(--color-border)] overflow-hidden transition-all"
      style={{
        width: panelWidth,
        height: panelHeight,
        transitionDuration: 'var(--motion-duration-slow)',
      }}
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]"
        style={{ backgroundColor: config.color }}
      >
        <div className="flex items-center gap-2 text-white">
          <span className="text-lg">{config.icon}</span>
          <span className="font-medium">{config.title}</span>
          {scopeId && (
            <span className="text-xs opacity-75">({scopeId.slice(0, 8)}...)</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleMinimize}
            className="p-1.5 rounded hover:bg-white/20 transition-colors"
            title="Thu nhỏ"
          >
            <Minimize2 className="w-4 h-4 text-white" />
          </button>
          <button
            onClick={handleExpand}
            className="p-1.5 rounded hover:bg-white/20 transition-colors"
            title={state.isExpanded ? "Thu gọn" : "Mở rộng"}
          >
            <Maximize2 className="w-4 h-4 text-white" />
          </button>
          <button
            onClick={handleClose}
            className="p-1.5 rounded hover:bg-white/20 transition-colors"
            title="Đóng"
          >
            <X className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[var(--color-bg-secondary)]">
        {messages.length === 0 && (
          <div className="text-center text-[var(--color-text-tertiary)] py-8">
            <span className="text-4xl">{config.icon}</span>
            <p className="mt-2 text-sm">Hãy đặt câu hỏi về {config.title.toLowerCase()}</p>
          </div>
        )}
        
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] px-4 py-2.5 rounded-xl text-sm ${
                msg.role === 'user'
                  ? 'bg-[var(--color-primary)] text-white rounded-br-sm'
                  : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-bl-sm'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              
              {/* Action Proposals */}
              {msg.proposedActions && msg.proposedActions.length > 0 && (
                <div className="mt-3 space-y-2">
                  {msg.proposedActions.map((action) => (
                    <ActionProposalCard
                      key={action.proposal_id}
                      proposal={{
                        action_id: action.proposal_id,
                        action_type: action.action_type,
                        description: action.description,
                        status: 'proposed',
                        requires_confirmation: true,
                      }}
                      onStatusChange={(newStatus) => handleActionConfirmed(action.proposal_id, newStatus)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 px-4 py-2.5 bg-[var(--color-bg-elevated)] rounded-xl border border-[var(--color-border)]">
              <Loader2 className="w-4 h-4 animate-spin text-[var(--color-primary)]" />
              <span className="text-sm text-[var(--color-text-secondary)]">Đang suy nghĩ...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input */}
      <div className="p-3 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={config.placeholder}
            disabled={isLoading}
            className="flex-1 px-4 py-2.5 text-sm bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-[var(--color-border-focus)] focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:opacity-50 transition-all"
          />
          <button
            onClick={handleSendMessage}
            disabled={!input.trim() || isLoading}
            className="p-2.5 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ 
              backgroundColor: input.trim() ? config.color : 'var(--color-bg-tertiary)',
              color: input.trim() ? 'white' : 'var(--color-text-tertiary)',
            }}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
