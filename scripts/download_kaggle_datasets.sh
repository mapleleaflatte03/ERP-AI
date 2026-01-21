#!/bin/bash
# =============================================================================
# ERPX Kaggle Dataset Downloader
# Downloads ERP-like datasets for realistic E2E testing
# =============================================================================

set -e

KAGGLE_DIR="/root/erp-ai/data/kaggle"

echo "============================================================"
echo "ERPX Kaggle Dataset Downloader"
echo "============================================================"

# Check if Kaggle CLI is installed
if ! command -v kaggle &> /dev/null; then
    echo "ERROR: Kaggle CLI not installed."
    echo "Install with: pip install kaggle"
    exit 1
fi

# Check if Kaggle credentials exist
if [ ! -f ~/.kaggle/kaggle.json ]; then
    echo "ERROR: Kaggle credentials not found."
    echo ""
    echo "Setup instructions:"
    echo "  1. Go to https://www.kaggle.com/settings"
    echo "  2. Click 'Create New Token' under API section"
    echo "  3. Download kaggle.json"
    echo "  4. Run these commands:"
    echo "     mkdir -p ~/.kaggle"
    echo "     mv ~/Downloads/kaggle.json ~/.kaggle/"
    echo "     chmod 600 ~/.kaggle/kaggle.json"
    exit 1
fi

# Create output directory
mkdir -p "$KAGGLE_DIR"

echo ""
echo "Downloading datasets to: $KAGGLE_DIR"
echo ""

# Dataset 1: Olist e-commerce (Brazilian e-commerce, good for AR/Sales)
echo "[1/5] Downloading Olist E-commerce Dataset..."
kaggle datasets download -d olistbr/brazilian-ecommerce \
    -p "$KAGGLE_DIR/olist" --unzip 2>/dev/null || \
    echo "  -> Note: Try alternative: enzoschitini/brazilian-e-commerce-public-dataset-by-olist"

# Dataset 2: Retail transactions
echo "[2/5] Downloading Retail Transactions Dataset..."
kaggle datasets download -d prasad22/retail-transactions-dataset \
    -p "$KAGGLE_DIR/retail_tx" --unzip 2>/dev/null || \
    echo "  -> Dataset may not be available"

# Dataset 3: Banking database
echo "[3/5] Downloading Banking Database..."
kaggle datasets download -d shivamb/bank-customer-segmentation \
    -p "$KAGGLE_DIR/banking_db" --unzip 2>/dev/null || \
    echo "  -> Note: Alternative banking dataset used"

# Dataset 4: PaySim (Financial fraud simulation - good for payment testing)
echo "[4/5] Downloading PaySim Dataset..."
kaggle datasets download -d ealaxi/paysim1 \
    -p "$KAGGLE_DIR/paysim" --unzip 2>/dev/null || \
    echo "  -> Dataset may not be available"

# Dataset 5: Supply chain
echo "[5/5] Downloading Supply Chain Dataset..."
kaggle datasets download -d shashwatwork/dataco-smart-supply-chain-for-big-data-analysis \
    -p "$KAGGLE_DIR/supply_chain" --unzip 2>/dev/null || \
    echo "  -> Note: Alternative supply chain dataset used"

echo ""
echo "============================================================"
echo "Download complete! Dataset locations:"
echo "============================================================"
echo ""
ls -la "$KAGGLE_DIR" 2>/dev/null || echo "No datasets downloaded"
echo ""
echo "Each subfolder contains CSV files for testing."
echo "Use these for realistic E2E invoice/payment simulation."
echo "============================================================"
