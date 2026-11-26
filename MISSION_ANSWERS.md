# Day 14 · Kết quả thực hành

## Part 1 · Localhost và production

Trong Ubuntu, POST `/ask?question=Hello` ở bản develop trả về `{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}`. Bản production nhận JSON qua POST /ask, trả cả question, answer và model. Khi đặt PORT=18001, /ready trả true và /health báo status ok, version 1.0.0.

| Quan sát trong develop/app.py | Thay đổi ở production | Tác dụng |
|---|---|---|
| API key và URL cơ sở dữ liệu nằm trong mã nguồn | Config đọc từ môi trường | Tách bí mật khỏi lịch sử Git |
| Dòng 34 in cả key ra console | Handler chỉ ghi độ dài câu hỏi và kết quả | Giảm rò rỉ qua log |
| DEBUG=True và reload=True | DEBUG điều khiển reload | Tránh khởi động lại worker khi đang phục vụ |
| Bind localhost, port cố định 8000 | HOST và PORT cấu hình được | Router của nền tảng gọi được container |
| Thiếu probe | /health và /ready | Phân biệt tiến trình sống với khả năng nhận tải |
| Thiếu xử lý vòng đời | Lifespan chuyển cờ readiness ở startup và shutdown | Có điểm để khởi tạo và đóng tài nguyên |

## Part 2 · Docker

1. Base image của develop là `python:3.11`, cung cấp Linux và Python cho những layer sau.
2. `WORKDIR /app` đặt thư mục làm việc cho các lệnh build tiếp theo và tiến trình lúc chạy.
3. Copy requirements trước source để Docker dùng lại layer cài thư viện khi chỉ đổi mã ứng dụng.
4. CMD cung cấp lệnh hoặc đối số mặc định. ENTRYPOINT đặt executable chính, các đối số khi chạy container có thể thay CMD.

Build từ gốc repo rồi đo bằng `docker image inspect --format '{{.Size}}' my-agent:develop my-agent:advanced`. Develop **1.667.779.962 byte (1.667,78 MB)**, production **239.815.562 byte (239,82 MB)**, giảm **85,6%**. Bản multi-stage chỉ đưa dependencies đã cài sang runtime slim. Container develop đã trả lời câu Hello qua query.

```text
Client → Nginx → agent
                   ├── Redis (cache/session)
                   └── Qdrant (vector store)
```

Chạy project Compose k5-day14-docker. GET /health qua cổng 80 của Nginx trả status ok, version 2.0.0 và uptime_seconds 3.2.

## Part 3 · Cloud

Agent Part 6 chạy tại https://day14-agent-haleduy.onrender.com. Render Blueprint khai báo cả web service, Redis và tham chiếu kết nối. Railway TOML mô tả cách build, khởi động và kiểm tra service, còn biến kết nối Redis được cấu hình trên nền tảng.

Pipeline Cloud Build cài dependencies và gọi pytest. Bước build gắn tag theo commit SHA và latest, rồi push image lên registry. Bước deploy chọn image theo SHA, đặt region, CPU, RAM, giới hạn replica và ánh xạ secret cho Cloud Run. Trong file mẫu, lệnh echo sau pytest có thể che exit code lỗi khi shell chưa bật `set -e`.

## Part 4 · API Gateway

Bản develop nhận header X-API-Key. Bản production cấp JWT tại POST /auth/token cho tài khoản demo student. Dùng Bearer token trên cùng một cửa sổ một phút cho 11 lần POST /ask.

Output của `curl -i` khi chạy lại trong Ubuntu ngày 26/11/2026.

**Develop, thiếu API key**

```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 08:31:08 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

**Develop, API key hợp lệ**

```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:31:08 GMT
server: uvicorn
content-length: 122
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

**Production, lần thứ 10 với cùng JWT**

```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:31:11 GMT
server: uvicorn
content-length: 178
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":0,"budget_remaining_usd":0.00019}}
```

**Production, lần thứ 11 với cùng JWT**

```http
HTTP/1.1 429 Too Many Requests
date: Thu, 26 Nov 2026 08:31:11 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795681931
retry-after: 59
content-length: 98
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Ở lượt đo ban đầu, GET /me/usage ghi nhận 10 request, 20 input token, 288 output token và chi phí 0,000176 USD. Rate limit giới hạn tần suất, còn cost guard cộng chi phí token theo giá input/output và kiểm tra ngân sách trước lần gọi tiếp theo. Một request dài vẫn có thể tốn nhiều tiền ngay cả khi tần suất thấp.

## Part 5 · Scaling và reliability

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`, sau đó chạy `python test_stateless.py`. Cùng một session đi qua các instance theo thứ tự 7c4ad6, c28d1a, 58d9c6, 7c4ad6, c28d1a. History trả đủ **10 tin nhắn cho 5 lượt hỏi đáp**. Mỗi worker đọc lại history từ Redis. Nếu lưu riêng trong RAM, worker kế tiếp chỉ thấy phần hội thoại của chính nó.

Liveness kiểm tra tiến trình. Readiness kiểm tra khả năng nhận traffic, kể cả kết nối Redis. Khi nhận SIGTERM, Uvicorn chờ request đang xử lý rồi chạy cleanup của lifespan. Bài chấm Part 6 đã kiểm tra cả Redis mất kết nối và dừng container.

## Part 6 · Checklist Deliverable

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================

```

## AI log

Em đã đọc hướng dẫn của LAB, các checkpoint và yêu cầu nộp bài. Em nhờ AI giúp sắp xếp thứ tự thực hiện, góp ý ở những chỗ dễ nhầm và đối chiếu kết quả với rubric. Trong phiên triển khai, Codex cũng trực tiếp chỉnh code Part 6, cấu hình deploy, chạy các phép thử và hỗ trợ tổng hợp báo cáo. Bảng dưới ghi lại các quyết định của em và những lần em dùng AI trong quá trình làm bài.

| Giai đoạn | Phần em chủ động thực hiện | Nội dung trao đổi với AI và kết quả |
|---|---|---|
| Chuẩn bị môi trường | Em đọc yêu cầu chạy LAB trên Windows và yêu cầu kiểm tra Docker **ngay trong Ubuntu**, vì đây là terminal dùng để chạy bài chấm. | Codex thiết lập Ubuntu WSL2, Python 3.11 và chạy thử `hello-world`. Bước này xác nhận Python chạy trên Linux và Ubuntu kết nối được với Docker Engine. |
| Lên kế hoạch | Em yêu cầu xem kế hoạch cho đủ các Part trước khi triển khai. Em duyệt thứ tự làm **Part 6 trước Part 3** để dùng cùng một phiên bản agent cho cả bài chấm local và bản deploy. | AI đối chiếu thứ tự với `CHECKPOINTS.md`, chỉ ra những bằng chứng cần lưu ngay khi chạy, đặc biệt là output của bài chấm, baseline eval và ảnh dashboard khi có tải. |
| Triển khai trên Render | Em chọn Render, tự đăng nhập tài khoản và dùng bản fork cá nhân làm nguồn triển khai. | Sau khi agent đạt `PASS 12/12` ở local, Codex deploy và kiểm tra URL public. `/health` và `/ready` trả `200`. Với cùng câu hỏi `Hello`, `/ask` trả `401` khi thiếu key và `200` khi có key hợp lệ. |
| Đọc kết quả benchmark | Khi xem kết quả, em quan tâm hai điểm: phiên bản mới có giữ được các câu từng trả lời đúng hay không, và thêm replica cải thiện phần nào của thời gian phản hồi. | Hai file eval cho thấy v2 tăng từ **21/23 lên 23/23** sau khi bổ sung kiến thức về JWT và Kubernetes HPA, với danh sách regression rỗng. Hai CSV scaling cho thấy p95 giảm từ **1.300 ms xuống 270 ms**, và p99 giảm từ **2.100 ms xuống 1.700 ms** trong cùng điều kiện tải. |
| Rà soát trước khi nộp | Em yêu cầu đối chiếu **bản đã push** với `SUBMISSION.md`, `CHECKPOINTS.md`, `RUBRIC.md` và quy định dùng AI. Em cũng yêu cầu xem trước nội dung AI log để duyệt cách mô tả phần việc của mình. | Kết quả đối chiếu xác nhận repo có ba tài liệu nộp bài, 10 JSON, hai CSV và bảy ảnh. Sau review độc lập bằng Agy CLI (Neon Medium), Codex đối chiếu lại cột 99% trong hai CSV, sửa nhận xét về p99, bổ sung đơn vị MB và chạy lại Part 4 để lưu phản hồi HTTP. |
