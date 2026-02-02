# TEST_SMOKE_FLOWS.md - ERPX AI Kế Toán

**Version tested:** v2.0.0 (pending tag)  
**Date:** 2026-02-02  
**Tester:** System Maintainer  
**Branch:** feature/agent-analyze-hub

---

## Môi trường Test

| Service | URL | Status |
|---------|-----|--------|
| UI (Production) | http://localhost:3002 | ✅ Running |
| UI (Dev) | http://localhost:3000 | Available via `npm run dev` |
| API (Direct) | http://localhost:8000 | ✅ Healthy |
| API (Kong Gateway) | http://localhost:8080/api | ✅ Healthy |
| Keycloak | http://localhost:8180 | ✅ Healthy |

---

## Flow 1 – Upload → OCR → Journal Proposal → Approve

### Các bước test

1. **Đăng nhập**
   - [ ] Mở http://localhost:3002
   - [ ] Đăng nhập với user: `admin` / password: `admin123`
   - [ ] Xác nhận redirect về trang chủ

2. **Upload chứng từ**
   - [ ] Vào module "Chứng từ" (`/`)
   - [ ] Click "Tải lên" hoặc kéo thả file PDF/ảnh hóa đơn
   - [ ] Chờ upload hoàn tất

3. **Kiểm tra OCR**
   - [ ] Job tạo thành công (status: processing → success)
   - [ ] Document xuất hiện trong danh sách
   - [ ] Click vào document để xem preview
   - [ ] Kiểm tra thông tin trích xuất hiển thị (vendor, số HĐ, ngày, số tiền)

4. **Kiểm tra Journal Proposal**
   - [ ] Vào "Đề xuất hạch toán" (`/proposals`)
   - [ ] Thấy proposal được tạo tự động từ document vừa upload
   - [ ] Kiểm tra các dòng journal entry (debit/credit)

5. **Approve qua Copilot + UI**
   - [ ] Mở Copilot (`/copilot`)
   - [ ] Hỏi: "Liệt kê các đề xuất đang chờ duyệt"
   - [ ] Copilot dùng tool `get_pending_proposals` và trả về danh sách
   - [ ] Hỏi: "Duyệt đề xuất số X" (với X là ID proposal)
   - [ ] Copilot tạo action proposal (propose_approve)
   - [ ] UI hiển thị card xác nhận action
   - [ ] Click "Xác nhận" trên card
   - [ ] Kiểm tra proposal chuyển trạng thái → approved

### Kết quả

| Bước | Status | Ghi chú |
|------|--------|---------|
| Đăng nhập | ⏳ | |
| Upload | ⏳ | |
| OCR | ⏳ | |
| Proposal | ⏳ | |
| Approve | ⏳ | |

**Kết luận Flow 1:** ⏳ PENDING

---

## Flow 2 – Copilot đọc chứng từ

### Các bước test

1. **Mở document đã OCR**
   - [ ] Vào "Chứng từ" (`/`)
   - [ ] Chọn 1 document đã có extracted data

2. **Hỏi Copilot về nội dung**
   - [ ] Mở Copilot (`/copilot`)
   - [ ] Hỏi: "Hóa đơn số [ID] tổng bao nhiêu tiền?"
   - [ ] Kiểm tra Copilot gọi tool `get_document_content`
   - [ ] Xác nhận câu trả lời khớp với dữ liệu thực

3. **Các câu hỏi bổ sung**
   - [ ] "Nhà cung cấp là ai?"
   - [ ] "Ngày hóa đơn?"
   - [ ] "Mô tả chi tiết các dòng hàng?"

### Kết quả

| Câu hỏi | Tool được gọi | Đúng/Sai | Ghi chú |
|---------|---------------|----------|---------|
| Tổng tiền | ⏳ | ⏳ | |
| Nhà cung cấp | ⏳ | ⏳ | |
| Ngày hóa đơn | ⏳ | ⏳ | |

**Kết luận Flow 2:** ⏳ PENDING

---

## Flow 3 – Analyze (Reports + Dataset)

### Tab 1: Báo cáo (Reports)

1. **Truy cập module**
   - [ ] Vào "Analyze" (`/analyze`)
   - [ ] Tab "Báo cáo" được chọn mặc định

2. **Chạy report**
   - [ ] Chọn report "Tổng hợp nhà cung cấp" (vendor_summary)
   - [ ] Click "Chạy báo cáo"
   - [ ] Kiểm tra bảng kết quả hiển thị
   - [ ] Thử report "Monthly Summary" nếu có

### Tab 2: Data Analyze

1. **Upload Dataset**
   - [ ] Chuyển sang tab "Data Analyze"
   - [ ] Click "Upload Dataset"
   - [ ] Chọn file CSV hoặc XLSX nhỏ (< 5MB)
   - [ ] Chờ upload + processing
   - [ ] Dataset xuất hiện trong danh sách với status "ready"

2. **Chạy NL2SQL Query**
   - [ ] Nhập câu hỏi: "Tổng doanh thu theo tháng"
   - [ ] Click "Phân tích"
   - [ ] Kiểm tra kết quả trả về (bảng/dữ liệu)

### Kết quả

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| Reports - vendor_summary | ⏳ | |
| Reports - monthly | ⏳ | |
| Dataset upload | ⏳ | |
| NL2SQL query | ⏳ | |

**Kết luận Flow 3:** ⏳ PENDING

---

## Flow 4 – Document Preview OCR Overlay

### Các bước test

1. **Mở document có OCR boxes**
   - [ ] Vào "Chứng từ" (`/`)
   - [ ] Chọn document dạng ảnh (image/jpeg, image/png)
   - [ ] Click vào để mở preview

2. **Kiểm tra OCR Overlay**
   - [ ] Overlay bounding boxes hiển thị trên ảnh
   - [ ] Nút toggle "OCR: BẬT/TẮT" hoạt động
   - [ ] Boxes có màu xanh (mặc định)

3. **Kiểm tra Fields Panel**
   - [ ] Panel "Thông tin trích xuất" hiển thị bên phải
   - [ ] Các field hiển thị: vendor_name, invoice_number, invoice_date, total_amount
   - [ ] Hover vào field → boxes liên quan highlight màu cam
   - [ ] Nút toggle "Fields" ẩn/hiện panel

4. **Với PDF**
   - [ ] Mở document PDF
   - [ ] Preview PDF hiển thị đúng
   - [ ] Panel fields hiển thị (nếu có dữ liệu)

### Kết quả

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| OCR overlay on image | ⏳ | |
| Toggle OCR on/off | ⏳ | |
| Fields panel | ⏳ | |
| Hover highlight | ⏳ | |
| PDF preview | ⏳ | |

**Kết luận Flow 4:** ⏳ PENDING

---

## Flow 5 – Agent Action Hub (Confirm/Cancel)

### Các bước test

1. **Tạo Action Proposal qua Copilot**
   - [ ] Mở Copilot (`/copilot`)
   - [ ] Yêu cầu hành động cần xác nhận, ví dụ:
     - "Duyệt đề xuất #123"
     - "Từ chối chứng từ #456"
   - [ ] Copilot tạo action proposal

2. **Kiểm tra UI Card**
   - [ ] Card "Xác nhận hành động" xuất hiện trong chat
   - [ ] Hiển thị: loại action, mô tả, nút Xác nhận/Hủy

3. **Xác nhận Action**
   - [ ] Click "Xác nhận"
   - [ ] Card chuyển trạng thái → executed
   - [ ] Hiển thị kết quả thực thi

4. **Hủy Action**
   - [ ] Tạo action proposal mới
   - [ ] Click "Hủy"
   - [ ] Card chuyển trạng thái → cancelled

### Kết quả

| Chức năng | Status | Ghi chú |
|-----------|--------|---------|
| Create action proposal | ⏳ | |
| UI card display | ⏳ | |
| Confirm action | ⏳ | |
| Cancel action | ⏳ | |

**Kết luận Flow 5:** ⏳ PENDING

---

## Tổng kết Test

| Flow | Tên | Status |
|------|-----|--------|
| 1 | Upload → OCR → Proposal → Approve | ⏳ |
| 2 | Copilot đọc chứng từ | ⏳ |
| 3 | Analyze (Reports + Dataset) | ⏳ |
| 4 | Document Preview OCR Overlay | ⏳ |
| 5 | Agent Action Hub | ⏳ |

**Tổng:** 0/5 PASS | 0/5 PENDING | 0/5 FAIL

---

## Bugs / Issues phát hiện

| # | Flow | Mô tả | Severity | Status |
|---|------|-------|----------|--------|
| - | - | - | - | - |

---

## Hướng dẫn chạy test

### Yêu cầu
- Docker + docker compose đang chạy
- Services healthy (chạy `docker compose ps`)

### Bước 1: Khởi động môi trường
```bash
cd /root/erp-ai
docker compose up -d
# Chờ services healthy
docker compose ps
```

### Bước 2: Truy cập UI
- Production: http://localhost:3002
- Dev (nếu cần debug): 
  ```bash
  cd ui && npm run dev
  # Truy cập http://localhost:3000
  ```

### Bước 3: Mở Edge Tools trong VS Code
1. `Ctrl+Shift+P` → "Microsoft Edge Tools: Open"
2. Nhập URL: `http://localhost:3002`
3. Dùng browser panel trong VS Code để test

### Bước 4: Chạy từng flow theo checklist trên

---

*Last updated: 2026-02-02*
