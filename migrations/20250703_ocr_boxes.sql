-- Add OCR bounding boxes column to documents table
-- This stores the bounding boxes separately for efficient querying

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS ocr_boxes JSONB DEFAULT '[]'::jsonb;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS page_dimensions JSONB DEFAULT '{}'::jsonb;

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_documents_has_boxes 
ON documents ((ocr_boxes IS NOT NULL AND ocr_boxes != '[]'::jsonb));

COMMENT ON COLUMN documents.ocr_boxes IS 'OCR bounding boxes: [{bbox: [[x1,y1],[x2,y2],...], text: "...", confidence: 0.95, page: 1}]';
COMMENT ON COLUMN documents.page_dimensions IS 'Page dimensions: {width: 612, height: 792, pages: [{width, height}]}';
