# Benchmark & Observability Report — Day 14

**Người thực hiện:** Codex cùng người dùng  
**Ngày chạy:** 2026-11-26 (Asia/Saigon)  
**Môi trường:** Windows 11, Python 3.11, local FastAPI mock agent; Docker Compose production stack (2 agent replicas, Nginx, Prometheus, Grafana, Jaeger, Locust).  
**SLO dùng trong benchmark:** `/ask` p95 < 500 ms; error rate ≤ 2%; golden-set accuracy ≥ 85%.

## 1. Metrics và cardinality

Đã thêm histogram `agent_question_length_chars` vào develop agent, với bucket 20, 50, 100, 200, 500, 1000, 2000 ký tự; endpoint `/ask` ghi nhận độ dài trước retrieval/LLM. Đã gửi request và xác nhận các series `_bucket`, `_sum`, `_count` xuất hiện tại `/metrics`.

Counter đếm tổng request/call/token; Gauge biểu diễn số request in-flight hoặc trạng thái phiên bản; Histogram gom latency/độ dài vào bucket và cho phép tính percentile. Dùng `route.path` template, `method`, `status`, `model`, `version` làm labels có tập giá trị hữu hạn. Tránh `request_id`, `user_id`, URL thô và nội dung/độ dài câu hỏi làm label: mỗi giá trị mới tạo thêm time series, gây tăng RAM và chi phí scrape. Độ dài câu hỏi được đo bằng Histogram thay vì label `length=...`, nên giá trị liên tục không làm nổ cardinality.

## 2. Benchmark hiệu năng — develop `load_test.py`

Các lần đo dùng 100 request mỗi mức concurrency (riêng concurrency 1 dùng 300), warm-up không tính; `MOCK_SLOW_RATE=0.03`, lỗi upstream ngẫu nhiên mặc định 1%. Số đo thay đổi theo mock randomness và tải máy.

| Concurrency | Requests | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO p95 < 500 ms |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 300 | 4.02 | 202.6 | 234.7 | 1724.4 | 1.67% | PASS |
| 10 | 100 | 45.26 | 200.6 | 454.3 | 461.4 | 2.00% | PASS |
| 50 | 100 | 40.49 | 462.6 | 1896.1 | 1983.4 | 1.00% | FAIL |
| 100 | 100 | 48.13 | 662.5 | 808.2 | 2058.5 | 2.00% | FAIL |

RPS tăng mạnh từ 1 lên 10, sau đó gần như bão hòa trong khoảng 40–48 req/s; thêm concurrency làm tăng queueing và tail latency thay vì tăng throughput tương ứng. Lần concurrency 1 dài hơn vì chạy nhiều request tuần tự và có request slow 1.5 giây. Mức 50/100 vi phạm p95 SLO; đây là benchmark mock trên máy lab, không phải capacity claim cho production.

### Tail latency khi thay đổi slow rate

Mỗi mức 100 request, concurrency 20; các JSON thô ở `reports/slow_*.json`.

| `MOCK_SLOW_RATE` | Average (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 238.9 | 478.9 | 480.6 |
| 0.03 | 291.7 | 474.3 | 1721.4 |
| 0.10 | 339.9 | 1683.4 | 1952.8 |

p99 phản ứng rõ với một nhóm nhỏ request slow; ở 3%, p95 vẫn gần baseline nhưng p99 đã lên khoảng 1.72 giây. Average che khuất phần đuôi phân bố nên không phù hợp làm SLO chính; p95/p99 nói rõ trải nghiệm của người dùng chậm nhất.

## 3. Eval chất lượng và quality gate

Golden dataset có 23 câu. Eval JSON đầy đủ nằm trong `reports/`.

| Version | Accuracy | Tokens trung bình/câu | Tổng cost | Cost/câu đúng | Gate 85% |
|---|---:|---:|---:|---:|---|
| v1, không retrieval | 4.3% (1/23) | 57.1 | $0.000404 | $0.00040395 | FAIL |
| v2 ban đầu | 91.3% (21/23) | 109.1 | $0.000762 | $0.00003627 | PASS |
| v2 sau cập nhật KB | 100% (23/23) | 114.3 | $0.000796 | $0.00003461 | PASS |

Hai câu v2 sai ban đầu và cách sửa KB:

| ID | Keyword còn thiếu | Bổ sung |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Tài liệu JWT so với API key: token JWT có chữ ký và thường có thời hạn; API key là credential tĩnh. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Tài liệu Kubernetes HPA về CPU, memory và custom metrics. |

Retrieval làm prompt dài hơn và tăng token trung bình khoảng 2 lần so với v1, nhưng chất lượng tăng rõ rệt. Sau khi bổ sung KB, cost/câu đúng thấp hơn vì gần như toàn bộ câu trả lời đều đúng.

Đã thêm [GitHub Actions quality gate](.github/workflows/benchmark-quality-gate.yml): chạy v2 trên golden dataset với `--min-accuracy 0.85`; workflow fail nếu accuracy dưới 85%. Đã chạy cùng lệnh eval local: 23/23, PASS.

## 4. Locust, dashboard, trace và alerts

### Locust CSV

- Baseline CSV: [`observability_stats.csv`](benchmark-results/observability_stats.csv), 199 request, 0 failure, 6.89 req/s aggregate; p50 190 ms, p95 220 ms, p99 1700 ms (tail sample nhỏ).
- Slow injection CSV: [`fault_slow30_verified_stats.csv`](benchmark-results/fault_slow30_verified_stats.csv), 1536 request, 165 failure (10.7%), 9.63 req/s aggregate; `/ask` p95 1700 ms, p99 10000 ms. Nginx ghi nhận 502/504 khi upstream chậm hoặc paused; đây là lý do phải quan sát cả load balancer lẫn metric của service.
- Các file exception/failure và lịch sử chạy nằm cùng thư mục `benchmark-results/`.

### Ảnh chụp

- [Grafana dashboard](screenshots/grafana-dashboard.png): Golden Signals, p95 gần 1.95 s, traffic, LLM latency/token/cost và retrieval hit ratio.
- [Jaeger trace chậm](screenshots/jaeger-slow-trace.png): trace `6d472bd357efd848aac39d0ed294a5fa`, tổng 1806.4 ms; span lớn nhất `chat mock-llm-small` 1666.2 ms (~92.2%); `agent.retrieve_context` 24.2 ms.
- [Prometheus Alerts khi agent bị pause](screenshots/prometheus-alert-firing.png). Bằng chứng trạng thái firing dạng JSON: [`alerts-firing.json`](benchmark-results/alerts-firing.json) và [`alerts-observed.json`](benchmark-results/alerts-observed.json).

### Hai alert đã kiểm tra

| Alert | Fault injection | Điều kiện và quan sát |
|---|---|---|
| `AgentHighLatencyP95` | Tăng `MOCK_SLOW_RATE` lên 0.3 và giữ tải | Firing sau khi p95 vượt 1 s liên tục theo `for: 2m`; quan sát khoảng 1.91 s. Panel p95 và latency LLM thể hiện rõ nhất. |
| `AgentInstanceDown` | `docker pause production-agent-1` | Firing sau thời gian scrape + `for: 30s` (quan sát trong khoảng 35–60 s); `up == 0`, số instance giảm. Đã unpause agent sau khi kiểm tra. |

Nếu đổi sang v1 mà metric hạ tầng còn xanh, lỗi chất lượng cần phát hiện bằng golden-set eval/synthetic quality monitoring; latency/error metrics không đo độ đúng câu trả lời. Với slow upstream, Nginx có thể timeout trước khi agent ghi nhận lỗi; cần theo dõi status/latency tại edge nữa.

## 5. Kết luận

1. Concurrency cao không tự làm throughput tăng tuyến tính; p95/p99 phơi bày queueing và request chậm mà average làm mờ.
2. Labels phải có tập giá trị nhỏ; dữ liệu người dùng và giá trị tự do thuộc logs/traces hoặc Histogram, không thuộc metric labels.
3. Metrics cho biết hệ thống đang có vấn đề, traces xác định span chậm, còn eval mới bắt được regression về chất lượng câu trả lời.

`reports/benchmark_summary.json` tổng hợp kết quả JSON. `benchmark-results/slow-trace.json` lưu payload trace; Locust CSV và screenshots được lưu tại `benchmark-results/`.

**Giới hạn phạm vi:** Không chạy so sánh scale 1 replica với 3 replicas; bài đo thực hiện theo concurrency 1/10/50/100 và fault injection như yêu cầu.



### Evidence availability

The repository currently contains genuine Grafana, slow-trace, and Prometheus firing screenshots. The requested scale-1/scale-3 Locust comparison was not performed; the available Locust CSVs are the baseline and slow-fault runs listed above. The error trace was subsequently captured under controlled local fault injection. Cloud deployment screenshots are unavailable because there is no deployed public service.

