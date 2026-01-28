import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Send,
  Bot,
  User,
  RefreshCw,
  Sparkles,
  BookOpen,
  HelpCircle,
  Copy,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import api from '../lib/api';
import type { ChatMessage } from '../types';

const SUGGESTED_QUESTIONS = [
  'Giải thích định khoản mua hàng chịu VAT 10%',
  'Khi nào dùng TK 641 vs TK 642?',
  'Hạch toán chiết khấu thương mại như thế nào?',
  'Cách phân biệt chi phí trả trước ngắn hạn và dài hạn?',
  'Quy định về lưu trữ chứng từ kế toán?',
];

export default function CopilotChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '0',
      role: 'assistant',
      content: 'Xin chào! Tôi là Trợ lý AI Kế toán. Tôi có thể giúp bạn:\n\n• Giải thích các bút toán và định khoản\n• Tra cứu quy định kế toán\n• Tư vấn nghiệp vụ kế toán\n• Phân tích chứng từ\n\nBạn cần hỗ trợ gì?',
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: (message: string) => api.sendCopilotMessage(message),
    onSuccess: (response) => {
      const assistantMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.content || response.message || 'Xin lỗi, tôi không thể xử lý yêu cầu này.',
        citations: response.citations,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, assistantMessage]);
    },
    onError: (error) => {
      // Show actual error - no mock response
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Không thể kết nối đến dịch vụ AI. Vui lòng kiểm tra:\n\n• Backend API đang hoạt động\n• LLM provider đã được cấu hình\n\nLỗi: ${error instanceof Error ? error.message : 'Unknown error'}`,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
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

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    chatMutation.mutate(input.trim());
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
  };

  const handleCopyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  return (
    <div className="h-[calc(100vh-180px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Trợ lý AI Kế toán</h1>
            <p className="text-sm text-gray-500">Hỏi đáp nghiệp vụ, giải thích bút toán</p>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
          <Sparkles className="w-4 h-4 text-green-600" />
          <span className="text-sm text-green-700">Powered by LLM</span>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user' 
                  ? 'bg-blue-600' 
                  : 'bg-gradient-to-br from-blue-500 to-purple-600'
              }`}>
                {msg.role === 'user' ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <Bot className="w-4 h-4 text-white" />
                )}
              </div>
              <div className={`max-w-[70%] ${msg.role === 'user' ? 'text-right' : ''}`}>
                <div className={`rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}>
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                </div>
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {msg.citations.map((cite, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs"
                      >
                        <BookOpen className="w-3 h-3" />
                        {cite}
                      </span>
                    ))}
                  </div>
                )}
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-2 mt-2">
                    <button
                      onClick={() => handleCopyMessage(msg.content)}
                      className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600"
                      title="Sao chép"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button
                      className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-green-600"
                      title="Hữu ích"
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      className="p-1.5 hover:bg-gray-100 rounded text-gray-400 hover:text-red-600"
                      title="Không hữu ích"
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {chatMutation.isPending && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-gray-100 rounded-2xl px-4 py-3">
                <RefreshCw className="w-4 h-4 animate-spin text-gray-500" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Questions */}
        {messages.length <= 1 && (
          <div className="px-4 pb-4">
            <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
              <HelpCircle className="w-3 h-3" />
              Câu hỏi gợi ý:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedQuestion(q)}
                  className="px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border rounded-full text-sm text-gray-700 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="p-4 border-t bg-gray-50">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Nhập câu hỏi về nghiệp vụ kế toán..."
              className="flex-1 px-4 py-3 border rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={chatMutation.isPending}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || chatMutation.isPending}
              className="px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {chatMutation.isPending ? (
                <RefreshCw className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2 text-center">
            AI có thể mắc lỗi. Vui lòng kiểm tra thông tin quan trọng.
          </p>
        </div>
      </div>
    </div>
  );
}
