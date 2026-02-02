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
  Upload,
  Paperclip,
  FileText,
  X,
  AlertCircle,
  Check,
} from 'lucide-react';
import api from '../lib/api';
import ActionProposalCard from '../components/ActionProposalCard';
import type { ChatMessage as BaseChatMessage } from '../types';

// Extended ChatMessage with action_proposals for Agent Hub
interface ChatMessage extends BaseChatMessage {
  action_proposals?: Array<{
    action_id: string;
    action_type: string;
    description: string;
    status: 'proposed' | 'executed' | 'cancelled' | 'failed';
    requires_confirmation: boolean;
  }>;
}

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
      content: 'Xin chào! Tôi là Trợ lý AI Kế toán. Tôi có thể giúp bạn:\n\n• Giải thích các bút toán và định khoản\n• Tra cứu quy định kế toán\n• Tư vấn nghiệp vụ kế toán\n• Phân tích chứng từ\n• Upload chứng từ để phân tích\n\nBạn cần hỗ trợ gì?',
      created_at: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // File upload state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showUploadConfirm, setShowUploadConfirm] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Allowed file types
  const ALLOWED_TYPES = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: (variables: { message: string, context?: any }) =>
      api.sendCopilotMessage(variables.message, variables.context),
    onSuccess: (response) => {
      const assistantMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        // Backend returns 'response' field
        content: response.response || response.content || 'Xin lỗi, tôi không thể xử lý yêu cầu này.',
        citations: response.citations,
        actions: response.actions, // Map legacy actions
        // Parse action_proposals from response (Agent Hub feature)
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
      setMessages(prev => [...prev, assistantMessage]);
    },
    onError: (error) => {
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
    chatMutation.mutate({ message: input.trim() });
  };

  const handleActionClick = (action: any) => {
    // Optimistic update or just trigger chat
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: `CONFIRM: ${action.label}`, // Show user what they clicked
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    // Call API with confirmed_action context
    chatMutation.mutate({
      message: "Confirmed",
      context: { confirmed_action: action }
    });
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
  };

  const handleCopyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };
  
  // File upload handlers
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    const validFiles = files.filter(file => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        alert(`File "${file.name}" không được hỗ trợ. Chỉ chấp nhận PDF, PNG, JPG.`);
        return false;
      }
      if (file.size > MAX_FILE_SIZE) {
        alert(`File "${file.name}" quá lớn. Giới hạn 10MB.`);
        return false;
      }
      return true;
    });
    
    if (validFiles.length > 0) {
      setSelectedFiles(prev => [...prev, ...validFiles]);
      setShowUploadConfirm(true);
    }
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
  
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    if (selectedFiles.length <= 1) {
      setShowUploadConfirm(false);
    }
  };
  
  const handleUploadConfirm = async () => {
    if (selectedFiles.length === 0) return;
    
    setIsUploading(true);
    const uploadedDocs: string[] = [];
    
    try {
      for (const file of selectedFiles) {
        setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));
        
        // Simulate progress
        const progressInterval = setInterval(() => {
          setUploadProgress(prev => ({
            ...prev,
            [file.name]: Math.min((prev[file.name] || 0) + 10, 90)
          }));
        }, 200);
        
        // Upload file
        const result = await api.uploadDocument(file);
        
        clearInterval(progressInterval);
        setUploadProgress(prev => ({ ...prev, [file.name]: 100 }));
        uploadedDocs.push(result.filename || file.name);
      }
      
      // Add success message to chat
      const successMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ Đã upload ${uploadedDocs.length} file thành công:\n\n${uploadedDocs.map(f => `• ${f}`).join('\n')}\n\nTôi đang phân tích chứng từ. Bạn có thể hỏi về nội dung các file này.`,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, successMessage]);
      
      // Reset state
      setSelectedFiles([]);
      setShowUploadConfirm(false);
      setUploadProgress({});
      
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `❌ Lỗi upload file: ${error instanceof Error ? error.message : 'Unknown error'}`,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsUploading(false);
    }
  };
  
  const handleUploadCancel = () => {
    setSelectedFiles([]);
    setShowUploadConfirm(false);
    setUploadProgress({});
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

      {/* Upload Confirmation Panel */}
      {showUploadConfirm && (
        <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Upload className="w-5 h-5 text-blue-600" />
              <h3 className="font-semibold text-blue-900">Xác nhận upload</h3>
            </div>
            <button
              onClick={handleUploadCancel}
              className="p-1 hover:bg-blue-100 rounded-lg transition-colors"
            >
              <X className="w-4 h-4 text-blue-600" />
            </button>
          </div>
          
          <div className="space-y-2 mb-4">
            {selectedFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-white rounded-lg border">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-700 truncate max-w-xs">{file.name}</span>
                  <span className="text-xs text-gray-400">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
                <div className="flex items-center gap-2">
                  {uploadProgress[file.name] !== undefined ? (
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${uploadProgress[file.name]}%` }}
                        />
                      </div>
                      {uploadProgress[file.name] === 100 && (
                        <Check className="w-4 h-4 text-green-500" />
                      )}
                    </div>
                  ) : (
                    <button
                      onClick={() => removeFile(index)}
                      className="p-1 hover:bg-gray-100 rounded"
                    >
                      <X className="w-4 h-4 text-gray-400" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex-1 flex items-center gap-2 text-xs text-blue-700">
              <AlertCircle className="w-4 h-4" />
              <span>File sẽ được upload và phân tích bởi AI</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleUploadCancel}
                disabled={isUploading}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
              >
                Hủy
              </button>
              <button
                onClick={handleUploadConfirm}
                disabled={isUploading || selectedFiles.length === 0}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Đang upload...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload ({selectedFiles.length} file)
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chat Area */}
      <div className="flex-1 bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user'
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
                <div className={`rounded-2xl px-4 py-3 ${msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-900'
                  }`}>
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                </div>

                {/* Actions */}
                {/* Action Proposals from Agent Hub */}
                {msg.action_proposals && msg.action_proposals.length > 0 && (
                  <div className="mt-2">
                    {msg.action_proposals.map((proposal) => (
                      <ActionProposalCard
                        key={proposal.action_id}
                        proposal={proposal}
                        onStatusChange={(newStatus, _result) => {
                          // Update message state when action is confirmed/cancelled
                          setMessages(prev => prev.map(m => 
                            m.id === msg.id 
                              ? {
                                  ...m,
                                  action_proposals: m.action_proposals?.map(p =>
                                    p.action_id === proposal.action_id
                                      ? { ...p, status: newStatus as any }
                                      : p
                                  )
                                }
                              : m
                          ));
                        }}
                      />
                    ))}
                  </div>
                )}

                {/* Legacy actions (old format) */}
                {/* Action Proposals from Agent Hub */}
                {msg.action_proposals && msg.action_proposals.length > 0 && (
                  <div className="mt-2">
                    {msg.action_proposals.map((proposal) => (
                      <ActionProposalCard
                        key={proposal.action_id}
                        proposal={proposal}
                        onStatusChange={(newStatus, _result) => {
                          // Update message state when action is confirmed/cancelled
                          setMessages(prev => prev.map(m => 
                            m.id === msg.id 
                              ? {
                                  ...m,
                                  action_proposals: m.action_proposals?.map(p =>
                                    p.action_id === proposal.action_id
                                      ? { ...p, status: newStatus as any }
                                      : p
                                  )
                                }
                              : m
                          ));
                        }}
                      />
                    ))}
                  </div>
                )}

                {/* Legacy actions (old format) */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="mt-2 flex flex-col gap-2">
                    {msg.actions.map(action => (
                      <div key={action.id} className="p-3 bg-white border rounded-lg shadow-sm">
                        <p className="text-sm font-medium text-gray-900 mb-2">{action.label}</p>
                        <button
                          onClick={() => handleActionClick(action)}
                          className={`w-full px-3 py-1.5 rounded text-sm font-medium text-white transition-colors ${action.style === 'danger' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
                            }`}
                        >
                          Xác nhận
                        </button>
                      </div>
                    ))}
                  </div>
                )}

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
                {/* Actions Tool bar for assistant */}
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
          {/* Hidden file input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            className="hidden"
          />
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-3 py-3 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors"
              title="Upload chứng từ"
              disabled={chatMutation.isPending || isUploading}
            >
              <Paperclip className="w-5 h-5" />
            </button>
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Nhập câu hỏi hoặc yêu cầu (VD: Duyệt phiếu số...)"
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
            Trợ lý có thể thực hiện tác vụ (duyệt, từ chối) khi được yêu cầu.
          </p>
        </div>
      </div>
    </div>
  );
}
