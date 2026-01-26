
import timeit
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.processing import extract_key_fields

SAMPLE_TEXT = """
CÔNG TY TNHH ABC
Địa chỉ: 123 Đường Nguyễn Huệ, Quận 1, TP.HCM
Mã số thuế: 0123456789
Điện thoại: 028 1234 5678

HÓA ĐƠN GIÁ TRỊ GIA TĂNG
(VAT INVOICE)

Mẫu số: 01GTKT0/001
Ký hiệu: AB/20E
Số: 0012345
Ngày: 15/01/2024

Đơn vị bán: Công ty Cổ phần Công nghệ XYZ
Mã số thuế: 9876543210
Địa chỉ: 456 Đường Lê Lợi, Quận 1, TP.HCM

Nội dung: Dịch vụ tư vấn phần mềm
Số lượng: 1
Đơn giá: 10.000.000
Thành tiền: 10.000.000

Cộng tiền hàng: 10.000.000
Thuế GTGT (10%): 1.000.000
Tổng cộng tiền thanh toán: 11.000.000
Số tiền viết bằng chữ: Mười một triệu đồng chẵn.
"""

def benchmark():
    # Warmup
    extract_key_fields(SAMPLE_TEXT)

    number = 10000
    time = timeit.timeit(lambda: extract_key_fields(SAMPLE_TEXT), number=number)
    print(f"Time for {number} iterations: {time:.4f} seconds")
    print(f"Average time per call: {time/number*1000:.4f} ms")

if __name__ == "__main__":
    benchmark()
