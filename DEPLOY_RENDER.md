# Triển khai lên Render (miễn phí)

Hướng dẫn đưa ứng dụng Flask (`app.py`) lên [Render](https://render.com) dạng **Web Service free**, để người khác truy cập qua URL công khai.

## Điều kiện

- Tài khoản GitHub (hoặc GitLab) và repo chứa **toàn bộ** mã nguồn thư mục dự án (gồm `app.py`, `requirements.txt`, `index.html`, …).
- Repo **public** thì free tier dễ dùng; repo private vẫn được nhưng có thể cần quyền trả phí tùy Render.

## Cách 1: Blueprint (có sẵn `render.yaml`)

1. Đăng nhập Render → **New** → **Blueprint**.
2. Chọn repository chứa project này.
3. Render đọc `render.yaml` → tạo Web Service `mo-phong-sir` (có thể đổi tên sau).
4. Bấm **Apply** và chờ build + deploy xong.
5. Mở URL dạng `https://mo-phong-sir.onrender.com` (tên cụ thể theo dashboard).

## Cách 2: Tạo Web Service thủ công

1. **New** → **Web Service** → Connect repository.
2. Cấu hình gợi ý:
   - **Runtime**: Python 3
   - **Build command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`  
     (hoặc để trống nếu dùng `Procfile` — Render tự nhận.)
   - **Instance type**: Free
3. **Environment** (biến môi trường):
   - `MPLBACKEND` = `Agg` (đồ thị matplotlib không cần màn hình).
4. **Advanced** → Python version: trùng với `runtime.txt` (ví dụ 3.11.8) nếu có.
5. Deploy.

## Hành vi quan trọng trên Render free

| Chủ đề | Ghi chú |
|--------|--------|
| **Ổ đĩa** | Ổ instance là **tạm**: redeploy / sleep có thể **mất** thư mục `output_*` và kết quả SIR. Người dùng nên **tạo lại dữ liệu** sau khi service cold start lâu. |
| **Sleep** | Free web **ngủ** khi không có traffic; lần mở đầu sau khi ngủ có thể **30–60 giây**. |
| **Timeout** | Gunicorn `--timeout 120`: mô phỏng lớn (nhiều node / nhiều ngày) có thể cần giảm tham số hoặc tăng timeout trên plan trả phí. |
| **RAM** | Giảm `num_users` khi «Tạo dữ liệu» nếu bị lỗi hết bộ nhớ. |

## Biến môi trường tùy chọn

| Biến | Ý nghĩa |
|------|--------|
| `MO_PHONG_OUTPUT_DIR` | Đường dẫn **tuyệt đối** tới một thư mục dataset `output_*` cố định (dùng khi cần trỏ sẵn một bộ dữ liệu). |
| `MO_PHONG_OUTPUT_ROOT` | Thư mục **cha**; generator sẽ tạo con `mo_phong_outputs/` bên trong (mặc định **không** cần trên Render). |
| `APP_HOST` | Chỉ dùng khi chạy `python app.py` cục bộ; trên Render dùng Gunicorn, không cần. |

Mặc định (sau chỉnh sửa code), dữ liệu sinh ra nằm **cùng thư mục code** (`output_*_users_*` ở root repo) để `get_latest_output_dir()` luôn tìm thấy — phù hợp Render.

## Kiểm tra sau khi deploy

1. Mở trang chủ `/` → dashboard tải được.
2. Bấm **Tạo dữ liệu** → chờ xong, đồ thị / API có dữ liệu.
3. Mở `/simulation` → chạy SIR nếu cần.

## Gỡ lỗi thường gặp

- **Build lỗi thiếu package**: thêm vào `requirements.txt` và push lại.
- **502 / Worker timeout**: giảm số user / số ngày mô phỏng; hoặc tăng `--timeout` (plan trả phí).
- **Module not found**: đảm bảo root repo là thư mục chứa `app.py` (không deploy nhầm thư mục cha).

## Bảo mật gợi ý

Ứng dụng đang `send_from_directory` phục vụ file tĩnh từ thư mục project — **không** đưa mật khẩu, token, hay dữ liệu nhạy cảm vào repo công khai.
