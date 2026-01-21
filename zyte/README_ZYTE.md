# Zyte Scrapy Cloud - ASOFT ERP-AI

> Scrapy project cho ERP-AI, deploy lên Zyte Scrapy Cloud.

## 📁 Cấu trúc thư mục

```
/root/erp-ai/zyte/
├── scrapy.cfg              # Scrapy project config
├── scrapinghub.yml         # Zyte deployment config (Project ID: 845063)
├── requirements.txt        # Dependencies cho Zyte
├── output.json             # Output từ local test
├── asoft_zyte/
│   ├── __init__.py
│   ├── items.py            # Item definitions (QuoteItem, InvoiceItem)
│   ├── settings.py         # Scrapy settings (safe defaults)
│   └── spiders/
│       ├── __init__.py
│       └── smoke_quotes.py # Smoke test spider
└── .venv/                  # Local virtual environment
```

## 🧪 Test Local

### 1. Khởi tạo environment

```bash
cd /root/erp-ai/zyte
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 2. Liệt kê spiders

```bash
scrapy list
# Output: smoke_quotes
```

### 3. Chạy spider local

```bash
# Output ra file JSON
scrapy crawl smoke_quotes -O output.json

# Hoặc chạy và xem log realtime
scrapy crawl smoke_quotes -L DEBUG
```

### 4. Kiểm tra output

```bash
head -50 output.json
# Hoặc
cat output.json | python3 -m json.tool | head -100
```

## 🚀 Deploy lên Zyte Scrapy Cloud

### 1. Cài shub

```bash
cd /root/erp-ai/zyte
source .venv/bin/activate
pip install -U shub
```

### 2. Login Zyte (INTERACTIVE - không lưu key vào file)

```bash
shub login
# Nhập API key khi được hỏi
# API key: <lấy từ Zyte Dashboard -> API keys>
```

> ⚠️ **QUAN TRỌNG**: KHÔNG commit API key vào repo. Key chỉ nhập qua `shub login`.

### 3. Deploy

```bash
shub deploy 845063
# 845063 = Zyte Project ID
```

Output thành công:
```
Deploying to project 845063
Deploy successful!
```

## 🎯 Chạy Job trên Zyte Dashboard

1. **Đăng nhập**: https://app.zyte.com/
2. **Vào project**: Click vào project `845063` hoặc tên bạn đặt
3. **Spiders tab**: Click "Spiders" ở sidebar
4. **Chạy spider**: 
   - Chọn `smoke_quotes`
   - Click **"Run"** button
5. **Xem job**:
   - Job list hiện ở **"Jobs"** tab
   - Click vào job ID để xem chi tiết

## 📊 Xem Logs & Output

### Trên Zyte Dashboard:

1. **Jobs → [job_id] → Logs**: Xem log realtime
2. **Jobs → [job_id] → Items**: Xem items đã scrape
3. **Jobs → [job_id] → Stats**: Xem thống kê (requests, items, errors)

### Qua CLI:

```bash
# Xem logs của job
shub log 845063/1/1

# Tải items về
shub items 845063/1/1 -o items.jl
```

## ⚙️ Đổi URL Target

### Cách 1: Sửa spider code

Edit file `asoft_zyte/spiders/smoke_quotes.py`:

```python
class SmokeQuotesSpider(scrapy.Spider):
    name = "smoke_quotes"
    allowed_domains = ["your-new-domain.com"]
    start_urls = ["https://your-new-domain.com/page"]
```

Sau đó re-deploy:
```bash
shub deploy 845063
```

### Cách 2: Truyền URL qua arguments (không cần re-deploy)

Sửa spider để nhận argument:

```python
def __init__(self, start_url=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if start_url:
        self.start_urls = [start_url]
```

Chạy với custom URL:
```bash
# Local
scrapy crawl smoke_quotes -a start_url="https://example.com"

# Trên Zyte Dashboard: thêm argument trong Run dialog
```

## 🔐 Security Notes

| Item | Trạng thái |
|------|-----------|
| API key trong repo | ❌ KHÔNG (interactive login) |
| Secrets trong code | ❌ KHÔNG |
| `.venv/` trong git | ❌ KHÔNG (đã có trong .gitignore) |
| `output/` trong git | ❌ KHÔNG |

## 📝 Settings Quan Trọng (settings.py)

```python
ROBOTSTXT_OBEY = True       # Tuân thủ robots.txt
DOWNLOAD_DELAY = 1          # 1 giây giữa requests
CONCURRENT_REQUESTS = 2     # Max 2 requests cùng lúc
AUTOTHROTTLE_ENABLED = True # Tự điều chỉnh tốc độ
CLOSESPIDER_ITEMCOUNT = 20  # Giới hạn 20 items (safety)
```

## 🆘 Troubleshooting

### Lỗi "shub: command not found"
```bash
source .venv/bin/activate
pip install -U shub
```

### Lỗi "No project found"
```bash
# Đảm bảo đang ở đúng thư mục
cd /root/erp-ai/zyte
ls scrapy.cfg  # Phải thấy file này
```

### Lỗi "Authentication failed"
```bash
shub logout
shub login  # Nhập lại API key
```

### Spider không chạy trên Zyte
- Kiểm tra requirements.txt có đủ dependencies
- Xem logs trên Dashboard để biết lỗi cụ thể

## 📚 Tài liệu tham khảo

- [Scrapy Documentation](https://docs.scrapy.org/)
- [Zyte Scrapy Cloud Docs](https://docs.zyte.com/scrapy-cloud/)
- [shub CLI Reference](https://shub.readthedocs.io/)

---

## 🔍 Spider: asoft_probe (API Discovery)

### Mục đích
Scan nhẹ trang public index.html để tìm:
- Internal links (`<a href>`)
- Script assets (`<script src>`)
- API endpoint hints (`/api/`, `/swagger`, `/v1/`, etc.)

### Safety Settings (KHÔNG thay đổi)
```python
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS = 1
CLOSESPIDER_PAGECOUNT = 15
DOWNLOAD_TIMEOUT = 10
```

### Chạy Local
```bash
cd /root/erp-ai/zyte
source .venv/bin/activate

# Default target
scrapy crawl asoft_probe -O output_probe.json

# Custom target
scrapy crawl asoft_probe -a base_url="http://example.com/index.html" -O output.json
```

### Chạy trên Zyte Dashboard
1. **Đăng nhập**: https://app.zyte.com/
2. **Project**: 845063
3. **Spiders** → `asoft_probe` → **Run**
4. (Optional) Thêm argument: `base_url=http://your-target.com/index.html`
5. **Jobs** → Click job ID → **Items** để xem kết quả

### Output Fields
| Field | Description |
|-------|-------------|
| `kind` | `page`, `link`, `script`, `api_hint` |
| `value` | URL hoặc API pattern tìm được |
| `source_url` | URL nơi phát hiện |
| `base_url` | Target gốc |

### ⚠️ Lưu ý
- Chỉ chạy **1 lần** khi cần discovery
- KHÔNG spam target
- Xem `api_hint` items để tìm endpoints

---

**Snapshot backup trước khi thêm Zyte**: `/root/erp-ai_snapshot_before_zyte.tar.gz`

**Zyte Project ID**: `845063`

**Spiders**: `smoke_quotes`, `asoft_probe`

**Last updated**: 2026-01-17
