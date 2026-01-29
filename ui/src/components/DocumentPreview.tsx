import { useState, useEffect, useRef } from 'react';
import { Layers, Maximize2, Loader2, AlertCircle } from 'lucide-react';
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
    fileUrl?: string; // Legacy
    documentId?: string; // New: preferred
    filename: string;
    contentType: string;
    ocrBoxes?: any[];
}

export default function DocumentPreview({ fileUrl, documentId, filename, contentType, ocrBoxes = [] }: DocumentPreviewProps) {
    const [showOverlay, setShowOverlay] = useState(true);
    const [blobUrl, setBlobUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const scale = 1;
    // Identify type based on content type
    const isImage = contentType.startsWith('image/');
    const isPDF = contentType === 'application/pdf';
    const isExcel = contentType.includes('spreadsheet') || contentType.includes('excel') || filename.endsWith('.xlsx') || filename.endsWith('.xls');

    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Fetch the file securely
    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);

        async function fetchFile() {
            try {
                // Determine effective URL
                let effectiveUrl = fileUrl;
                if (documentId) {
                    effectiveUrl = `/v1/documents/${documentId}/preview`;
                }

                if (!effectiveUrl) {
                    throw new Error("No file identifier provided");
                }

                // If it's already a blob url or external http, use it directly (optimization)
                if (effectiveUrl.startsWith('blob:') || effectiveUrl.startsWith('http')) {
                    if (active) {
                        setBlobUrl(effectiveUrl);
                        setLoading(false);
                    }
                    return;
                }

                // Phase 2.1: Excel Preview
                if (isExcel) {
                    const previewUrl = effectiveUrl.includes('?') ? `${effectiveUrl}&preview=true` : `${effectiveUrl}?preview=true`;
                    const response = await api.client.get(previewUrl);
                    // Backend returns HTML string if preview=true
                    if (active) {
                        setBlobUrl(response.data); // Store HTML string in blobUrl state for Excel
                        setLoading(false);
                    }
                    return;
                }

                // Fetch via API client to include Auth headers
                const blob = await api.getFileBlob(effectiveUrl);
                const objectUrl = URL.createObjectURL(blob);

                if (active) {
                    setBlobUrl(objectUrl);
                    setLoading(false);
                }
            } catch (err) {
                console.error("Failed to load file:", err);
                if (active) {
                    setError("Không thể xem trước file này (Lỗi quyền hoặc định dạng).");
                    setLoading(false);
                }
            }
        }

        fetchFile();

        return () => {
            active = false;
            // Only revoke if it's a real blob URL, not HTML string
            if (blobUrl && blobUrl.startsWith('blob:')) {
                URL.revokeObjectURL(blobUrl);
            }
        };
    }, [fileUrl, isExcel]);

    // ... (keep box logic) ...

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

    // Fallback for other types (Excel fallback if blobUrl null?)
    // ...

    // Normalize boxes
    const normalizedBoxes: OCRBox[] = ocrBoxes.map(box => {
        if (Array.isArray(box) && box.length >= 4) {
            return { x: box[0], y: box[1], w: box[2], h: box[3] };
        }
        return box as OCRBox;
    });

    const drawBoxes = () => {
        const canvas = canvasRef.current;
        const img = imgRef.current;
        if (!canvas || !img || !isImage) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = img.clientWidth;
        canvas.height = img.clientHeight;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!showOverlay) return;

        const scaleX = img.clientWidth / img.naturalWidth;
        const scaleY = img.clientHeight / img.naturalHeight;

        ctx.strokeStyle = '#3b82f6';
        ctx.lineWidth = 1.5;
        ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';

        normalizedBoxes.forEach(box => {
            const rx = box.x * scaleX;
            const ry = box.y * scaleY;
            const rw = box.w * scaleX;
            const rh = box.h * scaleY;

            ctx.beginPath();
            ctx.rect(rx, ry, rw, rh);
            ctx.stroke();
            ctx.fill();
        });
    };

    useEffect(() => {
        if (isImage && !loading && blobUrl) {
            window.addEventListener('resize', drawBoxes);
            return () => window.removeEventListener('resize', drawBoxes);
        }
    }, [isImage, showOverlay, ocrBoxes, loading, blobUrl]);

    const handleImageLoad = () => {
        if (isImage) drawBoxes();
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

    if (isPDF) {
        return (
            <div className="w-full h-full flex flex-col bg-white">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                        {filename}
                    </span>
                    <div className="flex gap-2">
                        <a href={blobUrl} target="_blank" rel="noreferrer" className="p-1.5 hover:bg-gray-200 rounded transition-colors" title="Mở tab mới">
                            <Maximize2 className="w-4 h-4 text-gray-600" />
                        </a>
                    </div>
                </div>
                <div className="flex-1 relative">
                    <iframe
                        src={`${blobUrl}#toolbar=0`}
                        className="w-full h-full border-none absolute inset-0"
                        title={filename}
                    />
                </div>
            </div>
        );
    }

    if (isImage) {
        return (
            <div className="w-full h-full flex flex-col overflow-hidden bg-gray-100">
                <div className="flex items-center justify-between px-4 py-2 bg-white border-b z-10 flex-shrink-0">
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate max-w-[200px]" title={filename}>
                        {filename}
                    </span>
                    <div className="flex gap-3">
                        <button
                            onClick={() => setShowOverlay(!showOverlay)}
                            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${showOverlay ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-gray-100 text-gray-500'
                                }`}
                        >
                            <Layers className="w-3.5 h-3.5" />
                            OCR: {showOverlay ? 'BẬT' : 'TẮT'}
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
        );
    }

    // Fallback for other types (Excel etc)
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
