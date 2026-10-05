# Lab 19 — Kết quả thực thi

Nguyễn Đức Minh · A20-K4 · 05/10/2026 (Asia/Bangkok)

Môi trường: Windows, Python 3.11.0, Lite; Qdrant in-memory, Feast SQLite,
`BAAI/bge-small-en-v1.5` (384 chiều), ONNX 2 luồng.
Dependencies chính: fastembed 0.8.1, qdrant-client 1.19.1, Feast 0.66.0.
Corpus/golden set được sinh lại với seed 42; không đổi nhãn hay query để tăng điểm.

## Bằng chứng theo notebook

| Notebook | Kết quả đo được | Bằng chứng |
|---|---|---|
| NB1 | 1.000 vector; paraphrase trả 5/5 doc `cloud` | [Output](logs/01_embeddings_index.txt), [ảnh](screenshots/01_embeddings_index_01.png) |
| NB2 | P@10: BM25 77,8%; vector 73,2%; hybrid 78,6%; mixed hybrid 100% | [Output](logs/02_hybrid_search_rrf.txt), [ảnh](screenshots/02_hybrid_search_rrf_01.png) |
| NB3 | API đúng schema; hybrid server-side P99 49,3 ms < 50 ms | [Output](logs/03_search_api_benchmark.txt), [ảnh](screenshots/03_search_api_benchmark_01.png) |
| NB4 | 3 view; materialize; online lookup hợp lệ; warm P99 1,55 ms; PIT 3 dòng đủ feature | [Output](logs/04_feast_feature_store.txt), [ảnh](screenshots/04_feast_feature_store_03.png) |
| NB5 | Filter 3,8%: post recall 0,00 vs filtered 1,00; fetch 500/1.000 mới phục hồi 1,00 | [Output](logs/05_filtered_search.txt), [ảnh](screenshots/05_filtered_search_01.png) |
| NB6 | Ngân sách 16: single-shot recall/balance 0,526/0,08; agent 0,922/0,92; +filter 0,839/0,75 | [Output](logs/06_agent_retrieval.txt), [ảnh](screenshots/06_agent_retrieval_01.png) |
| NB7 | Ngưỡng 0,75 sai 36%; 0,85 tiết kiệm đúng 100%, sai 0%; TTL/tenant isolation đúng | [Output](logs/07_semantic_cache.txt), [ảnh](screenshots/07_semantic_cache_01.png) |
| NB8 | Naive gap 0,477 vs in-fold −0,003; latest join rò 98,2%, AUC +0,120; ODFV ratio 0,03/4,21 | [Output](logs/08_feature_engineering.txt), [ảnh](screenshots/08_feature_engineering_01.png) |

NB4 có 3.000 / 300 / 200 dòng SQLite: mỗi entity có một dòng cho **mỗi feature**,
tương ứng 1.000 item × 3, 100 user × 3 và 100 user × 2. Đây là số dòng thật sau
materialization, không phải số entity. Các trang ảnh NB4 lưu cả apply và materialize.

## Chất lượng và giới hạn

| Slice | BM25 | Vector | Hybrid |
|---|---:|---:|---:|
| exact (15) | 96,7% | 88,7% | 96,7% |
| paraphrase (15) | 33,3% | 24,0% | 32,0% |
| mixed (20) | 97,0% | 98,5% | 100,0% |

Hybrid thắng trung bình và trên mixed. Riêng tiêu chí “vector thắng paraphrase”
không được tái hiện với model tiếng Anh mặc định: vector thấp hơn BM25 9,3 điểm.
Reflection ghi đúng số đo; chưa đo model đa ngữ nên không khẳng định mức cải thiện.
Điểm rubric cuối cùng do giảng viên quyết định, không tự xác nhận 100/100.

Các latency là phép đo local trên máy hiện tại, không phải SLA production.
NB3 đo 100 lượt/mode sau 10 lượt warm-up; P99 server-side không gồm network.
NB4 có cold lookup 39,45 ms, còn bảng 100 lượt warm đạt 1,55 ms P99.
Qdrant local lọc chính xác nhưng bỏ qua payload index/HNSW; kết quả NB5 chứng minh
recall, không chứng minh hiệu năng ANN ở quy mô production.
NB6 topic filter suy đoán loại bỏ doc liên quan ở topic khác, nên recall giảm.
NB7 false-hit là định nghĩa kiểm thử trên bộ probe, không bảo đảm 0% lỗi ngoài bộ này.

## Kiểm chứng và bonus

- [42 test pass](logs/tests.txt), [smoke test pass](logs/verify_lite.txt).
- Tám `.ipynb` trong `notebooks/` có output được giữ nguyên, không có cell error.
- [Reflection](REFLECTION.md) có 181 từ theo đếm khoảng trắng, dưới giới hạn 200.
- [Bonus architecture](../bonus/ARCHITECTURE.md) có sơ đồ, ba tradeoff, phương án
  bị bác bỏ và giới hạn POC; độ dài trên 600 từ.
- [Bonus demo](logs/bonus_demo.txt) chạy đủ năm truy vấn, dùng Feast thật, exit 0.
  Self-check xác minh lookup Kubernetes và isolation hai user.
- [Benchmark đầy đủ](logs/benchmark.txt): script mặc định đo 5.000 lượt/mode.

| Mode | P50 | P95 | P99 |
|---|---:|---:|---:|
| keyword | 1,7 ms | 2,5 ms | 3,2 ms |
| semantic | 12,1 ms | 17,8 ms | 23,3 ms |
| hybrid | 15,4 ms | 24,1 ms | 34,7 ms |

Benchmark đầy đủ exit 0; hybrid hơn BM25 0,8 điểm phần trăm và vector 5,4 điểm.
Phép đo này gọi trực tiếp Searcher; bảng REST server-side riêng nằm ở NB3.
Đã kiểm tra source `.py` khớp cell source `.ipynb`, mọi code cell có execution
count, không có error output, và cả tám notebook đều có ảnh bằng chứng.

## Chạy lại

Windows:

```powershell
powershell -File setup-lite.ps1
.venv/Scripts/python.exe scripts/execute_notebooks.py
.venv/Scripts/python.exe scripts/benchmark.py
.venv/Scripts/python.exe bonus/demo.py
.venv/Scripts/python.exe scripts/capture_evidence.py
```

Linux/macOS: `bash setup-lite.sh && make test && make notebooks && make benchmark`.
Runner notebook dừng với exit code khác 0 nếu cell lỗi, đồng thời giữ notebook và log
để chẩn đoán. Dependencies/model cần mạng ở lần tải đầu.

## Nộp bài

File và bằng chứng đã chuẩn bị trong workspace. Chưa push GitHub hoặc nộp LMS.
Theo README, cần public repo và paste URL vào ô Day 19 trên VinUni LMS;
giữ repo public đến khi công bố điểm. Remote hiện có:
`https://github.com/minhnd1307-tech/K4-Track2-Day19-VectorFeatureStore-Lab`.
