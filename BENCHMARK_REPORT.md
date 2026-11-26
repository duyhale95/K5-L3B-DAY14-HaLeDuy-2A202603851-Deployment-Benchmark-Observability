# Benchmark & Observability · Day 14

**Họ tên** Ha Le Duy
**Ngày đo** 26/11/2026
**Môi trường** Ubuntu 24.04 trên WSL2, Python 3.11.18. Docker Desktop cấp 8 CPU và khoảng 5,46 GiB RAM. Model và chi phí trong báo cáo đều là mô phỏng.

## 1. Mục tiêu dịch vụ

Bài load test dùng p95 ≤ 500 ms để phản ánh độ trễ của phần lớn người dùng và tỷ lệ lỗi ≤ 2% để giới hạn số lần gọi thất bại. Eval baseline yêu cầu đúng ≥ 80% trên golden dataset. Sau khi sửa hai tài liệu còn thiếu, gate cuối yêu cầu 100% và giữ được toàn bộ câu đã đúng.

## 2. Hiệu năng v2

Mỗi lượt gửi 300 request. Nguồn số liệu là bốn file `reports/load_v2_c*.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Lỗi | SLO |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.23 | 192.6 | 235.5 | 1697.3 | 1.33% | PASS |
| 10 | 33.75 | 194.2 | 417.1 | 1715.2 | 0.67% | PASS |
| 50 | 46.52 | 436.9 | 2819.1 | 3955.2 | 2.00% | FAIL |
| 100 | 46.29 | 979.9 | 4308.0 | 4910.0 | 0.67% | FAIL |

Từ 50 tới 100 request đồng thời, throughput gần như đứng yên ở 46 RPS trong khi p95 tăng từ 2,82 lên 4,31 giây. Kết quả phù hợp với việc request phải đợi lâu hơn khi hệ thống đã bão hòa. Lần đo này chưa tách riêng thời gian chờ phía client và server.

### Ảnh hưởng của request chậm

Giữ concurrency ở 20 và chỉ thay xác suất mô phỏng phản hồi chậm. Nguồn là ba file `reports/load_v2_slow_*.json`.

| MOCK_SLOW_RATE | Trung bình (ms) | p95 (ms) | p99 (ms) |
| --- | --- | --- | --- |
| 0 | 207.3 | 282.1 | 324.0 |
| 0.03 | 240.9 | 255.8 | 1688.5 |
| 0.1 | 376.3 | 1697.0 | 1711.0 |

Ở xác suất 3%, p99 đã vượt 1,6 giây trong khi p95 vẫn dưới 300 ms. Khi tăng lên 10%, cả p95 lẫn p99 đều trên 1,6 giây. Giá trị trung bình che bớt thời gian chờ mà nhóm người dùng này trải qua.

## 3. Chất lượng và chi phí

| Bản | Đúng / tổng | Token/câu | Tổng USD | USD/câu đúng | p95 (ms) | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | 1/23 | 58.0 | 0.000417 | 0.00041715 | 201.9 | FAIL |
| v2 | 21/23 | 109.0 | 0.000759 | 3.616e-05 | 222.6 | PASS |
| v2 sau sửa | 23/23 | 111.8 | 0.000775 | 3.37e-05 | 218.0 | PASS |

V1 ít token hơn nhưng chỉ trả lời đúng một câu. V2 bổ sung ngữ cảnh truy xuất, nên chi phí mỗi câu đúng thấp hơn dù tổng chi phí cao hơn. Hai mục bổ sung vào knowledge base giải quyết `security-02` (token JWT, chữ ký, hết hạn) và `scaling-03` (CPU, memory, custom metrics của HPA). Giữ nguyên golden dataset. So sánh với baseline v2 cho kết quả 23/23 và danh sách regression rỗng. Trong CI, chạy eval với `--baseline` và `--min-accuracy`, dùng exit code của bước này làm required check trước khi merge.

## 4. Quan sát hệ thống

[Grafana khi đang có tải](screenshots/grafana-dashboard.png) hiển thị 51,3 request/giây, lỗi 0,89%, p95 1,01 giây và 37 request đang xử lý. Trong một cửa sổ đo khác với 3 replica, Prometheus trả trung bình 238 ms và p95 296 ms. Ba instance nhận 18,21, 18,48 và 18,34 request/giây. Trong lần đo này Nginx chia tải khá đều. Input gồm cả câu hỏi và ngữ cảnh retrieval, nên số token đầu vào thường lớn hơn phần trả lời. Nginx trả 404 cho `/metrics` trên cổng 8080. Prometheus scrape trực tiếp từng agent trong mạng Docker.

### Hai cảnh báo đồng thời

Sau khi tiếp tục phiên, chạy lại Locust với 30 user, tăng 5 user/giây. Đặt `MOCK_ERROR_RATE=0.2` và `MOCK_SLOW_RATE=0.3` đồng thời, dùng một phiên Prometheus mới. Mốc 0 là ngay trước lệnh khởi động tải. Thời gian là lúc đầu tiên API báo firing, lấy mẫu khoảng 2 giây/lần.

| Thay đổi | Rule | Điều kiện duy trì | Thời gian quan sát |
|---|---|---|---|
| Tăng xác suất lỗi | AgentHighErrorRate | Tỷ lệ 5xx trên 5% trong 1 phút | 84.8 s |
| Tăng xác suất chậm | AgentHighLatencyP95 | p95 vượt 1 giây trong 2 phút | 145.2 s |

[Ảnh hai cảnh báo đang firing](screenshots/prometheus-alert-firing.png). Các panel tương ứng là Error rate và Latency p95. Bộ unit test rule của đề đã báo SUCCESS. Với lỗi chất lượng kiểu chuyển về v1, chỉ theo dõi HTTP 200 và latency có thể bỏ sót sự cố. Chạy eval định kỳ theo phiên bản và theo dõi retrieval hit ratio sẽ phát hiện trường hợp đó.

### Từ trace tới log

[Trace chậm](screenshots/jaeger-slow-trace.png) kéo dài 1.719,8 ms. Span con gọi model mất 1.694,4 ms, khoảng 98,5% tổng thời gian, còn retrieval mất 22,3 ms. [Trace lỗi](screenshots/jaeger-error-trace.png) trả HTTP 503 sau khoảng 121 ms. Log ứng dụng cùng trace ghi nhận lỗi từ mock LLM.

```jsonl
{"ts": "2026-11-26T14:44:53.003009+07:00", "level": "INFO", "service": "observable-agent", "instance": "02e1daa1ca8b", "event": "llm_call", "trace_id": "f9fd3d7a8fd6ba5cec73009611951d07", "span_id": "00e9658f03b51d4a", "request_id": "1a589e7cfe88", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1694.2}
{"ts": "2026-11-26T14:44:54.640059+07:00", "level": "INFO", "service": "observable-agent", "instance": "02e1daa1ca8b", "event": "llm_error", "trace_id": "dc8bf52f8e6957951ad074232a4fa42a", "span_id": "748bbae77e460e83", "request_id": "ecc50269b7b4", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Scaling

Locust headless, 100 user, tăng 10 user/giây, chạy 2 phút mỗi cấu hình. Bảng dùng dòng Aggregated trong hai CSV tại `benchmark-results/`, bao gồm cả /ask và /health.

| Replica | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Lỗi/tổng |
| --- | --- | --- | --- | --- | --- |
| 1 | 54.19 | 220 | 1300 | 2100 | 56/7025 |
| 3 | 60.36 | 190 | 270 | 1700 | 61/7821 |

Ba replica giảm p95 từ 1.300 xuống 270 ms và tăng throughput khoảng 11,4%. p99 vẫn ở 1.700 ms ở cả hai lần đo. Thêm replica xử lý được nhiều request đồng thời hơn, còn độ trễ cuộc gọi model vẫn xuất hiện ở phần đuôi phân phối.

## 6. Kết luận

- p99 bộc lộ các cuộc gọi chậm ngay cả khi p95 còn đạt SLO.
- Chi phí trên mỗi câu đúng cho thấy lợi ích của retrieval rõ hơn số token trung bình.
- Một trace liên kết với log qua trace_id xác định được phần thời gian nằm ở model. Trên production nên bổ sung cảnh báo khi accuracy của từng phiên bản giảm trên tập câu hỏi chuẩn.
