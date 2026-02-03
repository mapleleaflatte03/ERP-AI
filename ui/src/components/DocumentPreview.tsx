import { useState, useEffect, useRef } from 'react';
import { Layers, Maximize2, Loader2, AlertCircle, Eye, EyeOff, FileText, ChevronRight } from 'lucide-react';
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

interface ExtractedField {
    key: string;
    value: any;
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
    const [showOverlay, setShowOverlay] = useState(true);
    const [showFieldPanel, setShowFieldPanel] = useState(true);
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [hoveredField, setHoveredField] = useState<string | null>(null);

    const scale = 1;
    const isImage = contentType.startsWith('image/');
    const isPDF = contentType === 'application/pdf';
    const isExcel = contentType.includes('spreadsheet') || contentType.includes('excel') || filename.endsWith('.xlsx') || filename.endsWith('.xls');
    
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Fetch OCR boxes from API if documentId provided (for images and PDFs)
    const { data: ocrData } = useQuery({
        queryKey: ['ocr-boxes', documentId],
        queryFn: () => documentId ? api.getDocumentOcrBoxes(documentId) : null,
        enabled: !!documentId && (isImage || isPDF),
        staleTime: 60000,
    });

    // Fetch raw vs cleaned data
    const { data: fieldData } = useQuery({
        queryKey: ['raw-vs-cleaned', documentId],
        queryFn: () => documentId ? api.getDocumentRawVsCleaned(documentId) : null,
        enabled: !!documentId,
        staleTime: 60000,
    });

    // Merge boxes from props and API
    const boxes: OCRBox[] = ocrData?.boxes || initialBoxes.map((box: any) => {
        if (Array.isArray(box) && box.length >= 4) {
            return { x: box[0], y: box[1], w: box[2], h: box[3] };
        }
        return box as OCRBox;
    });

    const extractedFields: ExtractedField[] = fieldData?.cleaned_fields 
        ? Object.entries(fieldData.cleaned_fields).map(([key, value]) => ({
            key,
            value,
            confidence: fieldData.confidence?.[key]
        }))
        : [];

    // Page dimensions for scaling
    const pageDimensions = ocrData?.page_dimensions || { width: 1000, height: 1400 };

    // Fetch the file securely
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

    // Draw boxes on canvas
    const drawBoxes = () => {
        const canvas = canvasRef.current;
        const img = imgRef.current;
        if (!canvas || !img || !isImage) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = img.clientWidth;
        canvas.height = img.clientHeight;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!showOverlay || boxes.length === 0) return;

        const scaleX = img.clientWidth / (pageDimensions.width || img.naturalWidth);
        const scaleY = img.clientHeight / (pageDimensions.height || img.naturalHeight);

        boxes.forEach((box, _idx) => {
            const rx = box.x * scaleX;
            const ry = box.y * scaleY;
            const rw = box.w * scaleX;
            const rh = box.h * scaleY;

            // Different color for hovered field's boxes
            const isHighlighted = hoveredField && box.text?.toLowerCase().includes(String(fieldData?.cleaned_fields?.[hoveredField]).toLowerCase());
            
            if (isHighlighted) {
                ctx.strokeStyle = '#f59e0b';
                ctx.lineWidth = 2;
                ctx.fillStyle = 'rgba(245, 158, 11, 0.2)';
            } else {
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 1;
                ctx.fillStyle = 'rgba(59, 130, 246, 0.05)';
            }

            ctx.beginPath();
            ctx.rect(rx, ry, rw, rh);
            ctx.stroke();
            ctx.fill();
        });
    };

    useEffect(() => {
        if (isImage && !loading && blobUrl) {
            window.addEventListener('resize', drawBoxes);
            drawBoxes();
            return () => window.removeEventListener('resize', drawBoxes);
        }
    }, [isImage, showOverlay, boxes, loading, blobUrl, hoveredField]);

    const handleImageLoad = () => {
        if (isImage) drawBoxes();
    };

    // Format field value for display
    const formatFieldValue = (value: any): string => {
        if (value === null || value === undefined) return '-';
        if (typeof value === 'number') {
            return value.toLocaleString('vi-VN');
        }
        if (value instanceof Date || (typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/))) {
            try {
                return new Date(value).toLocaleDateString('vi-VN');
            } catch {
                return String(value);
            }
        }
        return String(value);
    };

    // Field label mapping
    const fieldLabels: Record<string, string> = {
        vendor_name: 'Nhà cung cấp',
        vendor_tax_id: 'Mã số thuế',
        invoice_number: 'Số hóa đơn',
        invoice_date: 'Ngày hóa đơn',
        total_amount: 'Tổng tiền',
        tax_amount: 'Thuế',
        currency: 'Tiền tệ',
        description: 'Mô tả',
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-12">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-2" />
                <p className="text-sm text-gray-500">Đang tải tài liệu...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-12 text-center">
                <AlertCircle className="w-10 h-10 text-red-400 mb-2" />
                <p className="text-gray-900 font-medium">Lỗi tải file</p>
                <p className="text-sm text-gray-500 mt-1">{error}</p>
            </div>
        );
    }

    if (!blobUrl) return null;

    // Excel preview
    if (isExcel && !loading && blobUrl) {
        return (
            <div className="w-full h-full flex flex-col bg-white">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                        {filename}
                    </span>
                    <a href={fileUrl} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
                        Tải file gốc
                    </a>
                </div>
                <div
                    className="flex-1 overflow-auto bg-gray-50 p-4"
                    dangerouslySetInnerHTML={{ __html: blobUrl }}
                />
            </div>
        );
    }

    // PDF preview with OCR data panel
    if (isPDF) {
        
        return (
            <div className="w-full h-full flex bg-white">
                <div className="flex-1 flex flex-col">
                    {/* Header with controls */}
                    <div className="flex items-center justify-between px-4 py-2 bg-white border-b">
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                            {filename}
                        </span>
                        <div className="flex gap-3">
                            {/* OCR Toggle for PDF */}
                            <button
                                onClick={() => setShowOverlay(!showOverlay)}
                                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                                    showOverlay ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-gray-100 text-gray-500'
                                }`}
                                title="Hiển thị văn bản OCR trích xuất từ PDF"
                            >
                                <Layers className="w-3.5 h-3.5" />
                                OCR: {showOverlay ? 'BẬT' : 'TẮT'}
                            </button>
                            {/* Fields Toggle */}
                            <button
                                onClick={() => setShowFieldPanel(!showFieldPanel)}
                                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                                    showFieldPanel ? 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200' : 'bg-gray-100 text-gray-500'
                                }`}
                                title="Hiển thị các trường đã trích xuất (OCR mapping)"
                            >
                                {showFieldPanel ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                                Fields
                            </button>
                            <div className="w-px h-4 bg-gray-200 my-auto"></div>
                            <a href={blobUrl} target="_blank" rel="noreferrer" className="p-1 hover:bg-gray-100 rounded" title="Xem gốc">
                                <Maximize2 className="w-4 h-4 text-gray-400" />
                            </a>
                        </div>
                    </div>
                    
                    {/* PDF iframe */}
                    <div className="flex-1 relative">
                        <iframe
                            src={`${blobUrl}#toolbar=0`}
                            className="w-full h-full border-none absolute inset-0"
                            title={filename}
                        />
                    </div>
                </div>
                
                {/* Side Panel: OCR Text or Fields */}
                {(showOverlay || showFieldPanel) && (
                    <div className="w-80 border-l bg-gray-50 overflow-auto flex flex-col">
                        {/* OCR Text Section */}
                        {showOverlay && (
                            <div className="border-b">
                                <div className="px-4 py-3 bg-white sticky top-0 border-b">
                                    <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                                        <Layers className="w-4 h-4 text-blue-500" />
                                        Văn bản OCR
                                    </h3>
                                    <p className="text-xs text-gray-500 mt-1">
                                        Nội dung đã nhận dạng từ tài liệu PDF
                                    </p>
                                </div>
                                <div className="p-3">
                                    {ocrData?.raw_text ? (
                                        <div className="bg-white rounded-lg border p-3 text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-auto font-mono text-xs">
                                            {ocrData.raw_text}
                                        </div>
                                    ) : boxes.length > 0 ? (
                                        <div className="bg-white rounded-lg border p-3 text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-auto font-mono text-xs">
                                            {boxes.map((box: any) => box.text).filter(Boolean).join('\n')}
                                        </div>
                                    ) : (
                                        <div className="text-center py-4 text-gray-400 text-sm">
                                            Chưa có dữ liệu OCR
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                        
                        {/* Fields Section */}
                        {showFieldPanel && (
                            <div className="flex-1">
                                <div className="px-4 py-3 bg-white sticky top-0 border-b">
                                    <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                                        <FileText className="w-4 h-4 text-emerald-500" />
                                        Thông tin trích xuất
                                    </h3>
                                    <p className="text-xs text-gray-500 mt-1">
                                        Các trường được AI nhận diện từ OCR
                                    </p>
                                </div>
                                <div className="p-3 space-y-2">
                                    {extractedFields.length > 0 ? (
                                        extractedFields.map((field) => (
                                            <div 
                                                key={field.key} 
                                                className="p-3 bg-white rounded-lg border hover:border-blue-200 transition-colors cursor-pointer"
                                                onMouseEnter={() => setHoveredField(field.key)}
                                                onMouseLeave={() => setHoveredField(null)}
                                            >
                                                <div className="text-xs text-gray-500 mb-1">{fieldLabels[field.key] || field.key}</div>
                                                <div className="font-medium text-gray-900">{formatFieldValue(field.value)}</div>
                                                {field.confidence && (
                                                    <div className="text-xs text-gray-400 mt-1">
                                                        Độ tin cậy: {(field.confidence * 100).toFixed(0)}%
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-8 text-gray-400">
                                            <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                            <p className="text-sm">Chưa có dữ liệu trích xuất</p>
                                            <p className="text-xs mt-1">Hệ thống sẽ tự động trích xuất sau khi xử lý OCR</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }

    // Image preview with OCR overlay
    if (isImage) {
        return (
            <div className="w-full h-full flex bg-gray-100">
                {/* Image with overlay */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2 bg-white border-b z-10 flex-shrink-0">
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                            {filename}
                        </span>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowOverlay(!showOverlay)}
                                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                                    showOverlay ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-gray-100 text-gray-500'
                                }`}
                            >
                                <Layers className="w-3.5 h-3.5" />
                                OCR: {showOverlay ? 'BẬT' : 'TẮT'}
                            </button>
                            <button
                                onClick={() => setShowFieldPanel(!showFieldPanel)}
                                className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                                    showFieldPanel ? 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200' : 'bg-gray-100 text-gray-500'
                                }`}
                            >
                                {showFieldPanel ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                                Fields
                            </button>
                            <div className="w-px h-4 bg-gray-200 my-auto"></div>
                            <a href={blobUrl} target="_blank" rel="noreferrer" className="p-1 hover:bg-gray-100 rounded" title="Xem gốc">
                                <Maximize2 className="w-4 h-4 text-gray-400" />
                            </a>
                        </div>
                    </div>

                    <div ref={containerRef} className="flex-1 overflow-auto p-8 flex items-center justify-center relative bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:20px_20px]">
                        <div className="relative shadow-2xl border border-gray-200 bg-white">
                            <img
                                ref={imgRef}
                                src={blobUrl}
                                alt={filename}
                                onLoad={handleImageLoad}
                                className="max-w-full h-auto block"
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

                {/* Fields Panel */}
                {showFieldPanel && (
                    <div className="w-80 border-l bg-white overflow-auto flex-shrink-0">
                        <div className="px-4 py-3 border-b bg-gray-50 sticky top-0 z-10">
                            <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                                <FileText className="w-4 h-4" />
                                Thông tin trích xuất
                            </h3>
                            {fieldData?.confidence && (
                                <p className="text-xs text-gray-500 mt-1">
                                    Độ tin cậy tổng: {(fieldData.confidence * 100).toFixed(0)}%
                                </p>
                            )}
                        </div>
                        
                        {extractedFields.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                                <p className="text-sm">Chưa có dữ liệu trích xuất</p>
                            </div>
                        ) : (
                            <div className="p-3 space-y-2">
                                {extractedFields.map((field) => (
                                    <div
                                        key={field.key}
                                        className={`p-3 rounded-lg border transition-all cursor-pointer ${
                                            hoveredField === field.key
                                                ? 'bg-amber-50 border-amber-200 ring-1 ring-amber-300'
                                                : 'bg-gray-50 border-gray-100 hover:bg-gray-100'
                                        }`}
                                        onMouseEnter={() => setHoveredField(field.key)}
                                        onMouseLeave={() => setHoveredField(null)}
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs text-gray-500">{fieldLabels[field.key] || field.key}</span>
                                            {field.confidence && (
                                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                                    field.confidence > 0.8 ? 'bg-green-100 text-green-700' :
                                                    field.confidence > 0.5 ? 'bg-yellow-100 text-yellow-700' :
                                                    'bg-red-100 text-red-700'
                                                }`}>
                                                    {(field.confidence * 100).toFixed(0)}%
                                                </span>
                                            )}
                                        </div>
                                        <div className="font-medium text-gray-900 mt-1">
                                            {formatFieldValue(field.value)}
                                        </div>
                                    </div>
                                ))}
                                
                                {/* Line Items if available */}
                                {fieldData?.line_items && fieldData.line_items.length > 0 && (
                                    <div className="mt-4 pt-4 border-t">
                                        <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
                                            <ChevronRight className="w-3 h-3" />
                                            Chi tiết ({fieldData.line_items.length} dòng)
                                        </h4>
                                        <div className="space-y-2">
                                            {fieldData.line_items.slice(0, 5).map((item: any, idx: number) => (
                                                <div key={idx} className="p-2 bg-gray-50 rounded text-xs">
                                                    <div className="font-medium text-gray-800 truncate">{item.description || item.name || `Dòng ${idx + 1}`}</div>
                                                    <div className="flex justify-between mt-1 text-gray-500">
                                                        <span>SL: {item.quantity || '-'}</span>
                                                        <span>{formatFieldValue(item.amount || item.total)}</span>
                                                    </div>
                                                </div>
                                            ))}
                                            {fieldData.line_items.length > 5 && (
                                                <p className="text-xs text-gray-400 text-center">
                                                    +{fieldData.line_items.length - 5} dòng khác
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }

    // Fallback for other types
    return (
        <div className="flex flex-col items-center justify-center h-full p-12 text-center bg-gray-50">
            <div className="bg-white p-8 rounded-3xl shadow-xl border border-gray-100 transition-all hover:scale-[1.02]">
                <div className="w-20 h-20 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-blue-100/50">
                    <Layers className="w-10 h-10 text-blue-500" />
                </div>
                <h3 className="font-bold text-gray-900 text-lg mb-1">{filename}</h3>
                <p className="text-sm text-gray-500 mb-6 uppercase tracking-widest">{contentType || 'Unknown File'}</p>
                <div className="flex flex-col gap-2">
                    <a
                        href={blobUrl}
                        download={filename}
                        className="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-medium shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 transition-all flex items-center justify-center gap-2"
                    >
                        Tải xuống để xem
                    </a>
                </div>
            </div>
        </div>
    );
}
