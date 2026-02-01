import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  X,
  FolderOpen,
  FileText,
  ChevronRight,
  Check,
  AlertCircle,
  Loader2,
  Upload,
  RefreshCw,
} from 'lucide-react';
import api from '../lib/api';

interface ServerImportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ServerDirectory {
  base_path: string;
  name: string;
  file_count: number;
  subdirectories: { path: string; name: string; file_count: number }[];
}

interface ServerFile {
  path: string;
  filename: string;
  size: number;
  modified: number;
  extension: string;
}

export default function ServerImportModal({ isOpen, onClose }: ServerImportModalProps) {
  const queryClient = useQueryClient();
  const [selectedPath, setSelectedPath] = useState<string>('');
  const [filePattern, setFilePattern] = useState('*');
  const [recursive, setRecursive] = useState(false);
  // selectedFiles state reserved for future multi-select feature
  const [, setSelectedFiles] = useState<Set<string>>(new Set());
  void setSelectedFiles; // Suppress unused warning

  // Fetch directories
  const { data: dirData, isLoading: loadingDirs } = useQuery({
    queryKey: ['server-directories'],
    queryFn: () => api.listServerDirectories(),
    enabled: isOpen,
  });

  // Fetch files when path selected
  const { data: filesData, isLoading: loadingFiles, refetch: refetchFiles } = useQuery({
    queryKey: ['server-files', selectedPath, filePattern],
    queryFn: () => api.listServerFiles(selectedPath, filePattern),
    enabled: isOpen && !!selectedPath,
  });

  // Import mutation
  const importMutation = useMutation({
    mutationFn: () => api.importFromServer(selectedPath, filePattern, recursive),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      if (data.data?.imported > 0) {
        onClose();
      }
    },
  });

  const directories: ServerDirectory[] = dirData?.data?.directories || [];
  const files: ServerFile[] = filesData?.data?.files || [];

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('vi-VN');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      
      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
              <FolderOpen className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Import từ Server</h2>
              <p className="text-sm text-gray-500">Chọn thư mục và file để import</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Directory Tree */}
          <div className="w-64 border-r overflow-y-auto p-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase mb-3">Thư mục</h3>
            {loadingDirs ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            ) : directories.length === 0 ? (
              <p className="text-sm text-gray-500">Không có thư mục được phép</p>
            ) : (
              <div className="space-y-1">
                {directories.map((dir) => (
                  <div key={dir.base_path}>
                    <button
                      onClick={() => setSelectedPath(dir.base_path)}
                      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm ${
                        selectedPath === dir.base_path
                          ? 'bg-blue-50 text-blue-700'
                          : 'hover:bg-gray-100 text-gray-700'
                      }`}
                    >
                      <FolderOpen className="w-4 h-4" />
                      <span className="flex-1 truncate">{dir.name}</span>
                      <span className="text-xs text-gray-400">{dir.file_count}</span>
                    </button>
                    {dir.subdirectories.map((sub) => (
                      <button
                        key={sub.path}
                        onClick={() => setSelectedPath(sub.path)}
                        className={`w-full flex items-center gap-2 px-3 py-2 pl-8 rounded-lg text-left text-sm ${
                          selectedPath === sub.path
                            ? 'bg-blue-50 text-blue-700'
                            : 'hover:bg-gray-100 text-gray-600'
                        }`}
                      >
                        <ChevronRight className="w-3 h-3" />
                        <span className="flex-1 truncate">{sub.name}</span>
                        <span className="text-xs text-gray-400">{sub.file_count}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Files List */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Filters */}
            <div className="flex items-center gap-4 p-4 border-b bg-gray-50">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Pattern:</label>
                <select
                  value={filePattern}
                  onChange={(e) => setFilePattern(e.target.value)}
                  className="px-3 py-1.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                >
                  <option value="*">Tất cả file</option>
                  <option value="*.pdf">PDF only</option>
                  <option value="*.xlsx">Excel only</option>
                  <option value="*.png">PNG only</option>
                  <option value="*.jpg">JPG only</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.target.checked)}
                  className="rounded"
                />
                Bao gồm thư mục con
              </label>
              <button
                onClick={() => refetchFiles()}
                className="ml-auto p-2 hover:bg-gray-200 rounded-lg"
                title="Làm mới"
              >
                <RefreshCw className="w-4 h-4 text-gray-500" />
              </button>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-y-auto p-4">
              {!selectedPath ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <FolderOpen className="w-12 h-12 mb-3 opacity-50" />
                  <p>Chọn thư mục để xem danh sách file</p>
                </div>
              ) : loadingFiles ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                </div>
              ) : files.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <FileText className="w-12 h-12 mb-3 opacity-50" />
                  <p>Không có file phù hợp</p>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm text-gray-500">
                      {files.length} file sẽ được import
                    </span>
                  </div>
                  {files.slice(0, 100).map((file) => (
                    <div
                      key={file.path}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 border"
                    >
                      <FileText className="w-5 h-5 text-gray-400" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {file.filename}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatSize(file.size)} • {formatDate(file.modified)}
                        </p>
                      </div>
                      <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                        {file.extension}
                      </span>
                    </div>
                  ))}
                  {files.length > 100 && (
                    <p className="text-center text-sm text-gray-500 py-2">
                      ... và {files.length - 100} file khác
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t bg-gray-50">
          <div className="text-sm text-gray-500">
            {selectedPath && files.length > 0 && (
              <span>
                Sẽ import <strong>{files.length}</strong> file từ{' '}
                <code className="px-1 py-0.5 bg-gray-200 rounded">{selectedPath}</code>
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-lg"
            >
              Hủy
            </button>
            <button
              onClick={() => importMutation.mutate()}
              disabled={!selectedPath || files.length === 0 || importMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {importMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang import...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Import {files.length} file
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result Message */}
        {importMutation.isSuccess && importMutation.data?.data && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 bg-green-100 text-green-800 rounded-lg shadow-lg flex items-center gap-2">
            <Check className="w-4 h-4" />
            Đã import {importMutation.data.data.imported} file thành công
          </div>
        )}
        {importMutation.isError && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 bg-red-100 text-red-800 rounded-lg shadow-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            Lỗi import: {(importMutation.error as Error)?.message}
          </div>
        )}
      </div>
    </div>
  );
}
