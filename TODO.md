# TODO - Deploy Render cho Mo_phong_SIR

- [x] Thêm `Procfile` để Render chạy gunicorn
- [x] Cập nhật `requirements.txt` thêm `gunicorn`
- [x] Sửa `app.py` để tạo thư mục khi dùng `MO_PHONG_OUTPUT_DIR`
- [x] Sửa `app.py` endpoint upload để ghi output vào `MO_PHONG_OUTPUT_DIR` thay vì BASE_DIR (ephemeral)
- [ ] Kiểm tra nhanh local: `python app.py` hoạt động (tuỳ chọn)
- [ ] Deploy lên Render: chọn Python Web Service, Build: `pip install -r requirements.txt`, Start dùng `Procfile`
- [ ] Set Environment Variable trên Render: `MO_PHONG_OUTPUT_DIR=/tmp/mo_phong_outputs` (hoặc thư mục tương ứng)
- [ ] Test endpoints `/`, `/simulation`, `/api/graph`, và nút Generate/Run SIR

