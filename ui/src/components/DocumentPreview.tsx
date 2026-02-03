import { useState, useEffect, useRef } from 'react';
import { Layers, Maximize2, Loader2, AlertCircle, FileText, Download } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';

interface OCRBox {
    x: number;
    y: number;
    w: number;
    h: number;
    text?: string;
    confidence?: number;
}

interface DocumentPreviewProps {
    fileUrl?: string;
    documentId?: string;
    filename: string;
    contentType: string;
    ocrBoxes?: any[];
}

export default function DocumentPreview({ fileUrl, documentId, filename, contentType, ocrBoxes: initialBoxes = [] }: DocumentPreviewProps) {
    // State
    const [showOverlay, setShowOverlay] = useState(true);
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // File type detection
    const isImage = contentType.startsWith('image/');
    const isPDF = contentType === 'application/pdf';
    const isExcel = contentType.includes('spreadsheet') || contentType.includes('excel') || filename.endsWith('.xlsx') || filename.endsWith('.xls');
    const fileType = isImage ? 'image' : isPDF ? 'pdf' : isExcel ? 'excel' : 'other';

    // Refs for image overlay
    const scale = 1;
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // OCR data for images and PDFs
    const { data: ocrData, isLoading: ocrLoading } = useQuery({
        queryKey: ['ocr-boxes', documentId],
        queryFn: () => documentId ? api.getDocumentOcrBoxes(documentId) : null,
        enabled: !!documentId && (isImage || isPDF),
        staleTime: 60000,
    });

    // Computed data
    const boxes: OCRBox[] = ocrData?.boxes || initialBoxes.map((box: any) => {
        if (Array.isArray(box) && box.length >= 4) {
            return { x: box[0], y: box[1], w: box[2], h: box[3] };
        }
        return box as OCRBox;
    });
    const pageDimensions = ocrData?.page_dimensions || { width: 1000, height: 1400 };

    // File loading
    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);

        async function fetchFile() {
            try {
                let effectiveUrl = fileUrl;
                if (documentId) {
                    effectiveUrl = `/v1/documents/${documentId}/preview`;
                }

                if (!effectiveUrl) {
                    throw new Error("No file identifier provided");
                }

                if (effectiveUrl.startsWith('blob:') || effectiveUrl.startsWith('http')) {
                    if (active) {
                        setBlobUrl(effectiveUrl);
                        setLoading(false);
                    }
                    return;
                }

                if (isExcel) {
                    const previewUrl = effectiveUrl.includes('?') ? `${effectiveUrl}&preview=true` : `${effectiveUrl}?preview=true`;
                    const response = await api.client.get(previewUrl);
                    if (active) {
                        setBlobUrl(response.data);
                        setLoading(false);
                    }
                    return;
                }

                const blob = await api.getFileBlob(effectiveUrl);
                const objectUrl = URL.createObjectURL(blob);
                if (active) {
                    setBlobUrl(objectUrl);
                    setLoading(false);
                }
            } catch (err) {
                console.error("Failed to load file:", err);
                if (active) {
                    setError("Không thể xem trước file này");
                    setLoading(false);
                }
            }
        }

        fetchFile();
        return () => {
            active = false;
            if (blobUrl && blobUrl.startsWith('blob:')) {
                URL.revokeObjectURL(blobUrl);
            }
        };
    }, [fileUrl, documentId, isExcel]);

    // Draw OCR boxes on canvas for images
    const drawBoxes = () => {
        const canvas = canvasRef.current;
        const img = imgRef.current;
        if (!canvas || !img || !isImage) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!showOverlay || boxes.length === 0) return;

        const scaleX = img.naturalWidth / pageDimensions.width;
        const scaleY = img.naturalHeight / pageDimensions.height;

        boxes.forEach((box) => {
            const x = box.x * scaleX;
            const y = box.y * scaleY;
            const w = box.w * scaleX;
            const h = box.h * scaleY;

            ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
            ctx.fillRect(x, y, w, h);
            ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, w, h);
        });
    };

    const handleImageLoad = () => {
        if (isImage) drawBoxes();
    };

    useEffect(() => {
        if (isImage) drawBoxes();
    }, [boxes, showOverlay, scale, pageDimensions]);

    // Shared Header
    const renderHeader = () => (
        <div className="flex items-center justify-between px-3 py-2 bg-white border-b flex-shrink-0">
            <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs font-medium text-gray-600 truncate max-w-[180px]" title={filename}>
                    {filename}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${
                    fileType === 'image' ? 'bg-purple-100 text-purple-700' :
                    fileType === 'pdf' ? 'bg-red-100 text-red-700' :
                    fileType === 'excel' ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-700'
                }`}>
                    {fileType.toUpperCase()}
                </span>
            </div>
            <div className="flex gap-2 items-center flex-shrink-0">
                {/* OCR Toggle - for Image and PDF */}
                {(isImage || isPDF) && (
                    <button
                        onClick={() => setShowOverlay(!showOverlay)}
                        className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-all ${
                            showOverlay ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-gray-100 text-gray-500'
                        }`}
                        title="Hiển thị OCR"
                    >
                        <Layers className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">OCR</span>
                    </button>
                )}
                
                <a 
                    href={isExcel ? fileUrl : blobUrl || ''} 
                    target="_blank" 
                    rel="noreferrer" 
                    className="p-1.5 hover:bg-gray-100 rounded" 
                    title="Mở trong tab mới"
                >
                    <Maximize2 className="w-4 h-4 text-gray-400" />
                </a>
            </div>
        </div>
    );

    // Loading state
    if (loading) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
                    <p className="mt-2 text-sm text-gray-500">Đang tải...</p>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
                    <p className="mt-2 text-sm text-red-600">{error}</p>
                </div>
            </div>
        );
    }

    // Excel preview
    if (isExcel && blobUrl) {
        return (
            <div className="w-full h-full flex flex-col bg-white">
                {renderHeader()}
                <div className="flex-1 overflow-auto bg-gray-50 p-4" dangerouslySetInnerHTML={{ __html: blobUrl }} />
            </div>
        );
    }

    // PDF preview with optional OCR panel
    if (isPDF && blobUrl) {
        return (
            <div className="w-full h-full flex flex-col bg-white">
                {renderHeader()}
                <div className="flex-1 flex min-h-0">
                    {/* PDF iframe */}
                    <div className="flex-1 relative">
                        <iframe
                            src={`${blobUrl}#toolbar=0`}
                            className="w-full h-full border-none absolute inset-0"
                            title={filename}
                        />
                    </div>
                    
                    {/* OCR Text Panel for PDF - collapsible */}
                    {showOverlay && (
                        <div className="w-64 border-l bg-gray-50 overflow-auto flex-shrink-0">
                            <div className="px-3 py-2 bg-white border-b sticky top-0">
                                <h3 className="font-medium text-gray-900 text-xs flex items-center gap-1.5">
                                    <Layers className="w-3.5 h-3.5 text-blue-500" />
                                    Văn bản OCR
                                </h3>
                            </div>
                            <div className="p-2">
                                {ocrLoading ? (
                                    <div className="flex items-center justify-center py-4">
                                        <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                                    </div>
                                ) : ocrData?.raw_text ? (
                                    <div className="bg-white rounded border p-2 text-xs text-gray-700 whitespace-pre-wrap max-h-[400px] overflow-auto font-mono leading-relaxed">
                                        {ocrData.raw_text}
                                    </div>
                                ) : (
                                    <div className="text-center py-4 text-gray-400 text-xs">
                                        Chưa có dữ liệu OCR
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Image preview with OCR overlay
    if (isImage && blobUrl) {
        return (
            <div className="w-full h-full flex flex-col bg-gray-100">
                {renderHeader()}
                <div 
                    ref={containerRef} 
                    className="flex-1 overflow-auto p-4 flex items-center justify-center"
                >
                    <div className="relative shadow-lg border border-gray-200 bg-white max-w-full max-h-full">
                        <img
                            ref={imgRef}
                            src={blobUrl}
                            alt={filename}
                            onLoad={handleImageLoad}
                            className="max-w-full max-h-[calc(100vh-200px)] h-auto block"
                            style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }}
                        />
                        {showOverlay && (
                            <canvas
                                ref={canvasRef}
                                className="absolute top-0 left-0 pointer-events-none"
                                style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }}
                            />
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Unsupported file type
    return (
        <div className="w-full h-full flex items-center justify-center bg-gray-50">
            <div className="text-center">
                <FileText className="w-12 h-12 text-gray-300 mx-auto" />
                <p className="mt-3 text-gray-600 font-medium">{filename}</p>
                <p className="text-sm text-gray-500 mt-1">Không hỗ trợ xem trước</p>
                {fileUrl && (
                    <a 
                        href={fileUrl} 
                        target="_blank" 
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 mt-4 px-3 py-1.5 bg-blue-50 text-blue-600 rounded text-sm hover:bg-blue-100"
                    >
                        <Download className="w-4 h-4" />
                        Tải xuống
                    </a>
                )}
            </div>
        </div>
    );
}
