#!/bin/bash
# OCR Demo Script for ERP AI
# Usage: ./run_ocr_demo.sh <path_to_pdf_or_image>

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base directories
ERP_AI_DIR="/root/erp-ai"
UPLOAD_DIR="$ERP_AI_DIR/data/uploads"
PROCESSED_DIR="$ERP_AI_DIR/data/processed"
VENV_DIR="$ERP_AI_DIR/venv"

echo "=============================================="
echo "  ERP AI - OCR Demo Script"
echo "=============================================="

# Check argument
if [ -z "$1" ]; then
    echo -e "${RED}Error: No input file provided${NC}"
    echo ""
    echo "Usage: $0 <path_to_pdf_or_image>"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/document.pdf"
    echo "  $0 /path/to/image.png"
    echo "  $0 /path/to/invoice.jpg"
    exit 1
fi

INPUT_FILE="$1"

# Check input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: File not found: $INPUT_FILE${NC}"
    exit 1
fi

# Get filename
FILENAME=$(basename "$INPUT_FILE")
echo -e "${YELLOW}Input file: $FILENAME${NC}"

# Check file type
EXT="${FILENAME##*.}"
EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

case $EXT_LOWER in
    pdf|png|jpg|jpeg|tiff|bmp)
        echo -e "${GREEN}File type: $EXT_LOWER (supported)${NC}"
        ;;
    *)
        echo -e "${RED}Error: Unsupported file type: $EXT${NC}"
        echo "Supported types: pdf, png, jpg, jpeg, tiff, bmp"
        exit 1
        ;;
esac

# Ensure directories exist
mkdir -p "$UPLOAD_DIR"
mkdir -p "$PROCESSED_DIR"

# Copy file to uploads directory
UPLOAD_PATH="$UPLOAD_DIR/$FILENAME"
if [ "$INPUT_FILE" != "$UPLOAD_PATH" ]; then
    echo "Copying to uploads directory..."
    cp "$INPUT_FILE" "$UPLOAD_PATH"
fi
echo -e "${GREEN}Upload path: $UPLOAD_PATH${NC}"

# Activate virtual environment and run OCR
echo ""
echo "----------------------------------------------"
echo "Starting OCR processing..."
echo "----------------------------------------------"

cd "$ERP_AI_DIR"
source "$VENV_DIR/bin/activate"

# Set environment variables
export DISABLE_MODEL_SOURCE_CHECK=True
export FLAGS_use_cuda=0
export CUDA_VISIBLE_DEVICES=""
export ERP_AI_DIR="$ERP_AI_DIR"

# Run OCR pipeline
python -m services.ocr.ocr_pipeline "$UPLOAD_PATH"

# Find the latest output file
echo ""
echo "----------------------------------------------"
echo "Output files:"
echo "----------------------------------------------"
LATEST_JSON=$(ls -t "$PROCESSED_DIR"/*.json 2>/dev/null | head -1)

if [ -n "$LATEST_JSON" ]; then
    echo -e "${GREEN}JSON output: $LATEST_JSON${NC}"
    echo ""
    echo "Preview (first 50 lines):"
    echo "----------------------------------------------"
    head -50 "$LATEST_JSON"
    echo ""
    echo "----------------------------------------------"
else
    echo -e "${YELLOW}No JSON output found${NC}"
fi

echo ""
echo -e "${GREEN}OCR Demo completed!${NC}"
echo "=============================================="
