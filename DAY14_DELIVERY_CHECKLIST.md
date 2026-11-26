# Day 14 Lab — Delivery Checklist

> **Student Name:** Đàm Hồng Thái
> **Student ID:** 2A202603927
> **Date:** 26/11/2026
> **Repository:** [K5-L3B-DAY14-DamHongThai-2A202603927-Deployment-Benchmark-Observability](https://github.com/itsbra1vo/K5-L3B-DAY14-DamHongThai-2A202603927-Deployment-Benchmark-Observability)
> **Submission status:** Bản nộp đã có nội dung và bằng chứng local; các mục cần deploy cloud, chạy checker trên Linux, và Locust scale 1/3 vẫn đang chờ.

---

## 1. Mission Answers — Part 1–5 (40 points)

Đã hoàn thiện câu trả lời trong [MISSION_ANSWERS.md](MISSION_ANSWERS.md), gồm:

- Part 1: anti-patterns, ý nghĩa và bảng so sánh develop/production.
- Part 2: Dockerfile, cache dependencies, `.dockerignore`, volume và giới hạn số đo image.
- Part 3: Render/Railway configuration; chưa tạo public deployment nên URL và ảnh deploy còn thiếu.
- Part 4: kết quả auth/rate limit/cost guard và giải thích bảo vệ API.
- Part 5: health/readiness, graceful shutdown, Redis/stateless và scaling.
- Phần AI usage log và kết quả checklist của `check_production_ready.py`.

## 2. Full Source Code — Lab 06 Complete (60 points)

Mã nguồn hoàn thiện nằm đúng vị trí cho lớp K5: [`06-lab-complete/`](06-lab-complete/). Bao gồm `app/`, `utils/`, `check_production_ready.py` (giữ nguyên script được cung cấp), Dockerfile đa tầng, Compose, requirements, `.env.example`, cấu hình Railway/Render và README.

Kết quả chạy đầy đủ checker với Docker ngày 2026-11-26:

- **11/12 tiêu chí; 40/40 checks passed; image 160 MB.**
- Docker stop test graceful shutdown đạt; phép thử SIGTERM trực tiếp không chạy được trong môi trường Windows, nên tổng kết checker vẫn là `CHƯA ĐẠT`, không phải `PASS 12/12`.
- API key, rate limiting, cost guard, health/readiness, Redis/stateless, logging và image được checker kiểm tra.
- Muốn xác nhận `PASS 12/12`, cần chạy script không có cờ quick mode trên Linux có Docker.

## 3. Service Domain Link

Thông tin triển khai và các lệnh kiểm tra được ghi trong [DEPLOYMENT.md](DEPLOYMENT.md). Root `render.yaml` và cấu hình Railway có mặt, nhưng **chưa triển khai service lên cloud**. Do đó chưa có public URL hoặc kết quả endpoint công khai để ghi nhận.

Kết quả local trong checker: health/readiness hoạt động; API thiếu/sai key trả 401, key hợp lệ trả 200; vượt hạn mức trả 429; hết ngân sách trả 402. Các kết quả local không thay thế kiểm tra URL cloud.

Ảnh dashboard deploy, service running và public test chưa có vì chưa tạo deployment. Không dùng ảnh giả hoặc URL mẫu làm bằng chứng.

## 4. Benchmark & Observability — Part 7 (20 points)

Báo cáo: [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). JSON ở [`reports/`](reports/), CSV/trace/alert evidence ở [`benchmark-results/`](benchmark-results/) và ảnh ở [`screenshots/`](screenshots/).

- Đã đo concurrency 1/10/50/100 và ghi RPS, p50/p95/p99, error rate, SLO; chi tiết từng mức ở báo cáo và JSON.
- Đã so sánh slow rate 0%, 3%, 10%.
- Eval golden set 23 câu: v1 **1/23 (4.3%)**, v2 ban đầu **21/23 (91.3%)**, v2 sau bổ sung knowledge **23/23 (100%)**. CI quality gate được đặt ở accuracy tối thiểu 85%.
- Bổ sung knowledge cho `security-02` và `scaling-03`; histogram `agent_question_length_chars` đã được thêm. Báo cáo nêu cách tránh cardinality cao trong metric labels.
- Có 4 ảnh Part 7: Grafana dashboard, Jaeger slow trace, Jaeger error trace, Prometheus alert firing.
- Hai alert đã quan sát firing: `AgentHighLatencyP95` (sau khoảng 2 phút theo cấu hình `for`) và `AgentInstanceDown` (khoảng 35–60 giây sau khi pause instance).
- Locust có baseline và slow-fault CSV. **Chưa tạo `scale_1_stats.csv` và `scale_3_stats.csv`**, nên không coi đây là kết quả so sánh scale.

## Pre-Submission Checklist

- [ ] Đã xác nhận repository public hoặc cấp quyền cho giảng viên. Remote hiện trỏ tới URL ở trên; visibility chưa được xác nhận trong môi trường này.
- [x] `MISSION_ANSWERS.md` có câu trả lời Part 1–5, AI log và kết quả checker.
- [ ] `DEPLOYMENT.md` có public URL hoạt động. Chưa deploy.
- [x] Source Part 6 ở `06-lab-complete/` theo cấu trúc K5.
- [x] `06-lab-complete/README.md` có hướng dẫn setup.
- [x] Không có `.env` được Git theo dõi; `.env.example` là file mẫu. Một `.env` cục bộ đang bị ignore/untracked: không force-add và xóa trước khi tạo archive chia sẻ.
- [x] Checker xác nhận cấu hình secrets/environment; không ghi secret thật vào báo cáo.
- [ ] Public URL truy cập được. Chưa deploy.
- [~] Có ảnh Part 7; còn thiếu ba ảnh deployment (`dashboard.png`, `running.png`, `test.png`).
- [x] Git history có các commit với nội dung rõ ràng.
- [ ] Checker `PASS 12/12`. Hiện tại 11/12 do phép thử SIGTERM Windows; cần chạy trên Linux.
- [~] Báo cáo Part 7 và artifact có mặt; Locust scale-1/scale-3 CSV chưa có.

> `[x]` hoàn tất; `[~]` có một phần bằng chứng; `[ ]` chưa hoàn tất.

## Self-Test — Kết quả thực tế

### Local checker

Chạy `python check_production_ready.py` tại `06-lab-complete/` với Docker: **11/12 tiêu chí, 40/40 checks passed, image 160 MB**. Lý do còn thiếu một tiêu chí được ghi tại Phần 2 và trong `MISSION_ANSWERS.md`.

### API và eval

Local Docker checker đã xác nhận các kết quả auth, rate limit, cost guard, health/readiness và stateless restart nêu trên. Eval v2 sau cập nhật knowledge đạt **23/23 (100%)**; CI gate yêu cầu tối thiểu 85%.

### Public endpoint checks

Chưa thể chạy vì chưa có domain cloud. Sau khi deploy, chạy các lệnh PowerShell trong `DEPLOYMENT.md` và điền kết quả thực tế cho `/health`, `/ready`, `/ask` không key và `/ask` có key. Không chụp ảnh có API key.

## Submission

Repository URL: <https://github.com/itsbra1vo/K5-L3B-DAY14-DamHongThai-2A202603927-Deployment-Benchmark-Observability>

Nộp link repo này trên LMS sau khi xử lý các mục còn `[ ]` và `[~]` ở checklist trên.

## Remaining work

1. Deploy Render/Railway, xác nhận quyền truy cập repo, ghi URL và kết quả endpoint, chụp ba ảnh deployment.
2. Chạy `check_production_ready.py` đầy đủ trên Linux có Docker để xác nhận `PASS 12/12`.
3. Chạy Locust với một và ba replicas để tạo `scale_1_stats.csv` và `scale_3_stats.csv`, rồi bổ sung so sánh vào báo cáo.

## Need Help?

- Xem [TROUBLESHOOTING.md](TROUBLESHOOTING.md) và [CODE_LAB.md](CODE_LAB.md).
- Quy định và tiêu chí chấm nằm trong [RULES.md](RULES.md) và [RUBRIC.md](RUBRIC.md).
