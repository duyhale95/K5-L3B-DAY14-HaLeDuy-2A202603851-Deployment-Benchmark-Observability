# Triển khai agent trên Render

**URL public** https://day14-agent-haleduy.onrender.com
**Bản đã deploy** `77ac7b1` trên nhánh main, Blueprint `06-lab-complete/render.yaml`. Web service Docker và Key Value dùng gói Free, cùng region Singapore.

| Biến | Nguồn |
|---|---|
| AGENT_API_KEY | Secret đặt khi tạo Blueprint |
| REDIS_URL | Connection string nội bộ của Key Value, Render cấp |
| ENVIRONMENT | production |
| PORT | Render cấp khi khởi động |

### Kiểm tra từ máy khách

Đặt AGENT_API_KEY trong môi trường shell bằng giá trị đã lưu ở Render. Các lệnh sau chỉ in mã HTTP.

```bash
BASE=https://day14-agent-haleduy.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

Kết quả quan sát lần lượt là **200, 200, 401, 200**. Ảnh dashboard, deploy và kết quả gọi public ở thư mục screenshots. Sau thời gian không hoạt động, lần gọi đầu có thể phải chờ instance Free khởi động.
