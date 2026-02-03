import { useState, useEffect, useRef } from 'react';
import { Layers, Maximize2, Loader2, AlertCircle, Eye, EyeOff, FileText, Download } from 'lucide-react';
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

// Field labels mapping - SHARED across all preview types
const fieldLabels: Record<string, string> = {
    vendor_name: 'Nhà cung cấp',
    vendor_tax_id: 'MST NCC',
    invoice_number: 'Số hóa đơn',
    invoice_date: 'Ngày hóa đơn',
    total_amount: 'Tổng tiền',
    vat_amount: 'Tiền VAT',
    pre_tax_amount: 'Tiền trước thuế',
    currency: 'Loại tiền',
    description: 'Mô tả',
    buyer_name: 'Người mua',
    buyer_tax_id: 'MST người mua',
    payment_method: 'Phương thức TT',
    bank_account: 'Tài khoản NH',
    serial: 'Ký hiệu',
    document_type: 'Loại chứng từ',
};

export default function DocumentPreview({ fileUrl, documentId, filename, contentType, ocrBoxes: initialBoxes = [] }: DocumentPreviewProps) {
    // === SHARED STATE ===
    const [showOverlay, setShowOverlay] = useState(true);
    const [showFieldPanel, setShowFieldPanel] = useState(true);
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [hoveredField, setHoveredField] = useState<string | null>(null);

    // === FILE TYPE DETECTION ===
    const isImage = contentType.startsWith('image/');
    const isPDF = contentType === 'application/pdf';
    const isExcel = contentType.includes('spreadsheet') || contentType.includes('excel') || filename.endsWith('.xlsx') || filename.endsWith('.xls');
    const fileType = isImage ? 'image' : isPDF ? 'pdf' : isExcel ? 'excel' : 'other';

    // === REFS (for image) ===
    const scale = 1;
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // === DATA FETCHING - UNIFIED FOR ALL TYPES ===
    // OCR data: available for images and PDFs
    const { data: ocrData, isLoading: ocrLoading } = useQuery({
        queryKey: ['ocr-boxes', documentId],
        queryFn: () => documentId ? api.getDocumentOcrBoxes(documentId) : null,
        enabled: !!documentId && (isImage || isPDF),
        staleTime: 60000,
    });

    // Extracted fields: available for ALL document types
    const { data: fieldData, isLoading: fieldLoading } = useQuery({
        queryKey: ['raw-vs-cleaned', documentId],
        queryFn: () => documentId ? api.getDocumentRawVsCleaned(documentId) : null,
        enabled: !!documentId,
        staleTime: 60000,
    });

    // === COMPUTED DATA ===
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

    const pageDimensions = ocrData?.page_dimensions || { width: 1000, height: 1400 };

    // === FILE LOADING ===
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

                // Excel: get HTML preview
                if (isExcel) {
                    const previewUrl = effectiveUrl.includes('?') ? `${effectiveUrl}&preview=true` : `${effectiveUrl}?preview=true`;
                    const response = await api.client.get(previewUrl);
                    if (active) {
                        setBlobUrl(response.data);
                        setLoading(false);
                    }
                    return;
                }

                // PDF/Image: get blob
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

    // === IMAGE: Draw OCR boxes on canvas ===
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

    // === SHARED COMPONENTS ===
    
    // Header with controls - SAME for all file types
    const renderHeader = () => (
        <div className="flex items-center justify-between px-4 py-2 bg-white border-b flex-shrink-0">
            <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                    {filename}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                    fileType === 'image' ? 'bg-purple-100 text-purple-700' :
                    fileType === 'pdf' ? 'bg-red-100 text-red-700' :
                    fileType === 'excel' ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-700'
                }`}>
                    {fileType.toUpperCase()}
                </span>
            </div>
            <div className="flex gap-2 items-center">
                {/* OCR Toggle - for Image and PDF */}
                {(isImage || isPDF) && (
                    <button
                        onClick={() => setShowOverlay(!showOverlay)}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                            showOverlay ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-gray-100 text-gray-500'
                        }`}
                        title="Hiển thị văn bản OCR"
                    >
                        <Layers className="w-3.5 h-3.5" />
                        OCR: {showOverlay ? 'BẬT' : 'TẮT'}
                    </button>
                )}
                
                {/* Fields Toggle - for ALL types */}
                <button
                    onClick={() => setShowFieldPanel(!showFieldPanel)}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${
                        showFieldPanel ? 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200' : 'bg-gray-100 text-gray-500'
                    }`}
                    title="Hiển thị thông tin trích xuất"
                >
                    {showFieldPanel ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                    Fields
                </button>
                
                <div className="w-px h-4 bg-gray-200"></div>
                
                {/* View original */}
                <a 
                    href={isExcel ? fileUrl : blobUrl || ''} 
                    target="_blank" 
                    rel="noreferrer" 
                    className="p-1 hover:bg-gray-100 rounded" 
                    title="Xem file gốc"
                >
                    <Maximize2 className="w-4 h-4 text-gray-400" />
                </a>
            </div>
        </div>
    );

    // OCR Text Panel - for PDF only (image shows overlay on canvas)
    const renderOcrPanel = () => {
        if (!isPDF || !showOverlay) return null;
        
        return (
            <div className="border-b">
                <div className="px-4 py-3 bg-white sticky top-0 border-b">
                    <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                        <Layers className="w-4 h-4 text-blue-500" />
                        Văn bản OCR
                    </h3>
                    <p className="text-xs text-gray-500 mt-1">
                        Nội dung đã nhận dạng từ tài liệu
                    </p>
                </div>
                <div className="p-3">
                    {ocrLoading ? (
                        <div className="flex items-center justify-center py-4">
                            <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                            <span className="ml-2 text-sm text-gray-500">Đang tải OCR...</span>
                        </div>
                    ) : ocrData?.raw_text ? (
                        <div className="bg-white rounded-lg border p-3 text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-auto font-mono text-xs">
                            {ocrData.raw_text}
                        </div>
                    ) : boxes.length > 0 ? (
                        <div className="bg-white rounded-lg border p-3 text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-auto font-mono text-xs">
                            {boxes.map((box: any) => box.text).filter(Boolean).join('\n')}
                        </div>
                    ) : (
                        <div className="text-center py-4 text-gray-400 text-sm">
                            <Layers className="w-6 h-6 mx-auto mb-2 opacity-50" />
                            Chưa có dữ liệu OCR
                        </div>
                    )}
                </div>
            </div>
        );
    };

    // Fields Panel - SAME for ALL file types
    const renderFieldsPanel = () => {
        if (!showFieldPanel) return null;

        return (
            <div className="w-80 border-l bg-white overflow-auto flex-shrink-0 flex flex-col">
                {/* For PDF: show both OCR and Fields in side panel */}
                {isPDF && renderOcrPanel()}
                
                {/* Fields section */}
                <div className="flex-1 flex flex-col">
                    <div className="px-4 py-3 bg-gray-50 border-b sticky top-0 z-10">
                        <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                            <FileText className="w-4 h-4 text-emerald-500" />
                            Thông tin trích xuất
                        </h3>
                        <p className="text-xs text-gray-500 mt-1">
                            Các trường đã nhận dạng từ tài liệu
                        </p>
                    </div>
                    
                    <div className="flex-1 overflow-auto">
                        {fieldLoading ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="w-5 h-5 animate-spin text-emerald-500" />
                                <span className="ml-2 text-sm text-gray-500">Đang tải...</span>
                            </div>
                        ) : extractedFields.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                                <p className="text-sm font-medium">Chưa có dữ liệu</p>
                                <p className="text-xs mt-1">Tài liệu chưa được xử lý hoặc không trích xuất được thông tin</p>
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
                                            {field.value !== null && field.value !== undefined && field.value !== ''
                                                ? String(field.value)
                                                : <span className="text-gray-400 italic">Không có</span>
                                            }
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    // === LOADING STATE ===
    if (loading) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
                    <p className="mt-2 text-sm text-gray-500">Đang tải {fileType}...</p>
                </div>
            </div>
        );
    }

    // === ERROR STATE ===
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

    // === EXCEL PREVIEW ===
    if (isExcel && blobUrl) {
        return (
            <div className="w-full h-full flex bg-white">
                <div className="flex-1 flex flex-col overflow-hidden">
                    {renderHeader()}
                    <div
                        className="flex-1 overflow-auto bg-gray-50 p-4"
                        dangerouslySetInnerHTML={{ __html: blobUrl }}
                    />
                </div>
                {renderFieldsPanel()}
            </div>
        );
    }

    // === PDF PREVIEW ===
    if (isPDF && blobUrl) {
        return (
            <div className="w-full h-full flex bg-white">
                <div className="flex-1 flex flex-col overflow-hidden">
                    {renderHeader()}
                    <div className="flex-1 relative">
                        <iframe
                            src={`${blobUrl}#toolbar=0`}
                            className="w-full h-full border-none absolute inset-0"
                            title={filename}
                        />
                    </div>
                </div>
                {renderFieldsPanel()}
            </div>
        );
    }

    // === IMAGE PREVIEW ===
    if (isImage && blobUrl) {
        return (
            <div className="w-full h-full flex bg-gray-100">
                <div className="flex-1 flex flex-col overflow-hidden">
                    {renderHeader()}
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
                {renderFieldsPanel()}
            </div>
        );
    }

    // === UNSUPPORTED FILE TYPE ===
    return (
        <div className="w-full h-full flex items-center justify-center bg-gray-50">
            <div className="text-center">
                <FileText className="w-12 h-12 text-gray-300 mx-auto" />
                <p className="mt-3 text-gray-600 font-medium">{filename}</p>
                <p className="text-sm text-gray-500 mt-1">Không hỗ trợ xem trước định dạng này</p>
                <p className="text-xs text-gray-400 mt-2">Content-Type: {contentType}</p>
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
