# Kiến Trúc Hệ Thống Bộ Nhớ Lai (Hybrid AI Memory) Cho Trợ Lý Cá Nhân Tiếng Việt

**Tác giả:** K4 Track 2 AI Engineer  
**Hệ thống:** Personal AI Memory POC (Vector Store + Feature Store)  
**Phiên bản:** 1.0 (Production Blueprint & Minimal POC)

---

## 1. Tổng Quan Kiến Trúc

Một trợ lý AI cá nhân thế hệ mới (Personal Copilot / Second Brain) không thể chỉ dựa vào một context window cố định hay thuần tuý vector search. Hệ thống cần hai loại trí nhớ bổ trợ lẫn nhau:
1. **Episodic Memory (Trí nhớ sự kiện / từng hồi):** Chứa các ghi chú, nhật ký hội thoại, tài liệu kỹ thuật mà người dùng đã đọc hoặc lưu. Dữ liệu phi cấu trúc, giàu ngữ nghĩa, tăng trưởng liên tục. Thành phần đảm trách: **Vector Store** (Qdrant) kết hợp **Sparse Lexical Search** (BM25) theo cơ chế **Hybrid Search RRF**.
2. **Stable Profile & Dynamic Velocity (Hồ sơ người dùng & Tốc độ hoạt động):** Chứa thông tin nhân khẩu học học máy (sở thích chủ đề, tốc độ đọc, ngôn ngữ ưu tiên, nhịp độ truy vấn theo thời gian thực). Dữ liệu dạng bảng (tabular/streaming), yêu cầu độ trễ cực thấp (< 10 ms). Thành phần đảm trách: **Feature Store** (Feast).

### Sơ Đồ Kiến Trúc Luồng Dữ Liệu (ASCII Architecture Diagram)

```
       [ Người dùng / User Input ]
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│               AI Assistant Gateway & Memory Orchestrator        │
└──────┬───────────────────────────────────────────────────┬──────┘
       │                                                   │
       │ (1) Ingestion Flow (remember)                     │ (2) Retrieval Flow (recall)
       ▼                                                   ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│    Text Chunking & Parsing    │           │    Feature Store Online Lookup│
│  (Whitespace Sliding Window)  │           │      (Feast / SQLite-Redis)   │
└──────────────┬────────────────┘           └──────────────┬────────────────┘
               │                                           │
               ▼                                           │ [user_id: u_001]
┌───────────────────────────────┐                          │ -> topic_affinity: "cloud"
│ Dense Embedder + BM25 Ingest  │                          │ -> reading_speed_wpm: 220
│ (BAAI/bge-small / bge-m3)     │                          │ -> queries_last_hour: 3
└──────────────┬────────────────┘                          │
               │                                           │
               ▼                                           ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│    Qdrant Vector Database     │◄──────────┤ Filtered Hybrid Search (RRF)  │
│  Collection: episodic_memory  │           │  (Dense ANN + BM25 Sparse)    │
│  Payload: {user_id, text, ts} │           │  Filter: must match user_id   │
└───────────────────────────────┘           └──────────────┬────────────────┘
                                                           │
                                                           │ Top-K episodic notes
                                                           ▼
                                            ┌───────────────────────────────┐
                                            │   Context Synthesis Engine    │
                                            │ (Profile + Velocity + Memory) │
                                            └──────────────┬────────────────┘
                                                           │
                                                           ▼
                                            ┌───────────────────────────────┐
                                            │    Assembled Prompt / LLM     │
                                            │  (Personalized, Grounded)     │
                                            └───────────────────────────────┘
```

---

## 2. Ba Quyết Định Kiến Trúc Then Chốt & Phân Tích Đánh Đổi (Tradeoffs)

### Quyết định 1: Chiến Lược Phân Đoạn (Chunking Strategy) Cho Episodic Memory
- **Lựa chọn áp dụng:** Cửa sổ trượt kích thước nhỏ (sliding window 60 words, overlap 15 words) cắt theo khoảng trắng (chưa có sentence segmentation tiếng Việt), gán metadata `user_id` và timestamp.
- **So sánh đánh đổi (X vs Y, tại sao chọn X):**
  - *Phương án X (Áp dụng):* Micro-chunking (60 từ + 15 từ overlap).
  - *Phương án Y (Xem xét):* Macro-chunking theo toàn bộ phiên hội thoại (Conversation-level, 500-1000 tokens).
  - *Lý do chọn X:* Trong episodic memory cá nhân, người dùng thường lưu những mẩu ghi chú ngắn hoặc câu hỏi mang tính sự kiện cụ thể ("cách cấu hình HPA trên K8s", "lưu ý Vault secret"). Khi dùng macro-chunking, vector embedding của cả phiên hội thoại bị "pha loãng" (vector averaging), làm giảm đáng kể điểm tương đồng Cosine đối với các truy vấn chi tiết hẹp. Micro-chunking tăng độ chính xác tìm kiếm (Precision@3), giảm dung lượng prompt context bơm vào LLM, giúp tiết kiệm chi phí inference và giữ context window gọn gàng. Chi phí tăng thêm về số lượng vector được bù đắp bởi tính năng filtered-ANN hiệu quả của Qdrant.

### Quyết định 2: Thiết Kế Feature Schema — Tabular Feast View vs Embedded Profile
- **Lựa chọn áp dụng:** Sử dụng 2 feature views dạng bảng rõ ràng (tabular schemas) trong Feast:
  1. `user_profile_features` (TTL = 30 ngày): `reading_speed_wpm` (Int64), `preferred_language` (String), `topic_affinity` (String).
  2. `query_velocity_features` (TTL = 1 giờ): `queries_last_hour` (Int64), `distinct_topics_24h` (Int64).
- **So sánh đánh đổi (X vs Y, tại sao chọn X):**
  - *Phương án X (Áp dụng):* Phân tách thuộc tính profile dạng bảng tường minh (explicit tabular features) trong Feast Feature Store.
  - *Phương án Y (Xem xét):* Biểu diễn toàn bộ lịch sử người dùng thành một "User Preference Embedding Vector" 1024-dim và lưu trong Vector DB.
  - *Lý do chọn X:* Biểu diễn dạng bảng mang tính tất định (deterministic), minh bạch và dễ kiểm soát theo quy định pháp lý (auditability). Khi cần điều chỉnh định dạng đầu ra (ví dụ: tốc độ đọc 220 wpm thì tóm tắt ngắn dưới 200 từ; ngôn ngữ ưu tiên là 'vi' thì sinh tiếng Việt), LLM hoạt động tốt nhất khi nhận được các chỉ dẫn số lượng và nhãn phân loại rõ ràng thay vì suy đoán từ một vector ẩn. Ngoài ra, TTL của các đặc trưng rất khác nhau (profile đổi theo tháng, velocity đổi theo phút) — Feature Store quản lý TTL độc lập từng view một cách tự nhiên.

### Quyết định 3: Chiến Lược Độ Tươi Dữ Liệu (Freshness Strategy)
- **Lựa chọn áp dụng:** Kiến trúc độ tươi phân tầng đa tốc độ (Multi-tier Freshness):
  - *Tier 1 (Sub-second / Real-time Ingestion):* Episodic memory (Vector Store upsert ngay lập tức khi user ghi chú hoặc kết thúc lượt chat).
  - *Tier 2 (Near Real-time / Streaming Push 1-minute):* Query velocity & fraud signals (`queries_last_hour`) qua Feast Push Source hoặc Streaming pipeline.
  - *Tier 3 (Batch Daily / Scheduled Materialization):* Topic affinity & reading speed tính toán qua batch job cuối ngày từ data warehouse.
- **So sánh đánh đổi (X vs Y, tại sao chọn X):**
  - *Phương án X (Áp dụng):* Phân tầng độ tươi theo bản chất nghiệp vụ.
  - *Phương án Y (Xem xét):* Đưa toàn bộ hệ thống về streaming thời gian thực 100% (Real-time updates cho mọi feature).
  - *Lý do chọn X:* Chi phí vận hành hạ tầng streaming phân tán (Kafka/Flink) là rất đắt đỏ. Sở thích người dùng (topic affinity) không thay đổi đột ngột sau 5 giây, việc tính toán lại sở thích theo thời gian thực chỉ gây lãng phí tài nguyên và tạo nhiễu. Ngược lại, việc ghi nhớ sự kiện (episodic memory) phải có tính tức thời để user hỏi lại ("tôi vừa nói gì?") nhận được câu trả lời chính xác ngay lập tức.

---

## 3. Lựa Chọn Bị Bác Bỏ (Rejected Alternative)

- **Giải pháp bị loại bỏ:** *Lưu trữ toàn bộ episodic memory dưới dạng on-demand feature view hoặc embedding column trong Feast Feature Store*.
- **Lý do bác bỏ chi tiết:**
  Feast là hệ thống tối ưu cho tra cứu điểm theo khóa định danh thực thể (`entity_key lookup` qua key-value store như Redis/DynamoDB/SQLite) với độ phức tạp O(1). Feast không sinh ra để thực hiện tìm kiếm gần đúng Approximate Nearest Neighbor (ANN) trên đồ thị HNSW qua hàng trăm nghìn vector. Việc cố nhồi nhét vector vào Feature Store rồi quét toàn bảng (table scan) sẽ phá hủy hoàn toàn cam kết độ trễ < 10 ms. Việc tách biệt chuyên trách: **Qdrant lo tìm kiếm tương đồng vector (ANN search)** và **Feast lo tra cứu hồ sơ định danh (Key-Value lookup)** là nguyên tắc phân tách trách nhiệm tối thượng trong hệ thống ML production.

---

## 4. Yếu Tố Ngữ Cảnh Tiếng Việt (Vietnamese-Context Considerations)

1. **Hiện tượng pha trộn ngôn ngữ (Code-Switching vi/en):**
   Người dùng kỹ thuật tại Việt Nam thường xuyên trộn lẫn tiếng Việt và thuật ngữ kỹ thuật tiếng Anh (ví dụ: *"deploy service lên k8s bị OOMKilled"*). Vì vậy, hệ thống sử dụng kết hợp BM25 sparse index (giữ nguyên keyword verbatim như `OOMKilled`, `k8s`) và dense vector model lite `bge-small-en-v1.5`; các model đa ngữ (`bge-m3` hoặc `multilingual-e5-large`) là hướng nâng cấp cần đo lại qua phép kết hợp RRF (Reciprocal Rank Fusion). Điều này đảm bảo không bị mất dấu keyword tiếng Anh chuyên ngành trong khi vẫn hiểu ngữ nghĩa tiếng Việt.
2. **Quy định bảo vệ dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP):**
   Episodic memory của người dùng cá nhân chứa dữ liệu nhạy cảm. POC thiết lập phân vùng dữ liệu mềm (Payload isolation filter `user_id` bắt buộc trong mọi truy vấn HNSW) trên cả nhánh dense và sparse. POC chưa triển khai xác thực, xóa dữ liệu hoặc kiểm chứng tuân thủ pháp lý; không coi payload filter là bằng chứng tuân thủ.

---

## 5. Giới Hạn Của Bản POC Hiện Tại (What This POC Doesn't Handle Yet)

Bản POC hiện tại tập trung chứng minh tính đúng đắn của việc kết hợp Vector Store và Feature Store. Các điểm cần mở rộng cho bản thương mại hóa gồm:
- **Mã hóa dữ liệu tại chỗ (Encryption at Rest):** Chưa hỗ trợ mã hóa từng vector payload theo khóa riêng của từng user (Per-user KMS Key).
- **Cơ chế quên và suy hao trí nhớ (Memory Decay & Consolidation):** Chưa có background worker tự động nén gộp (summarize) các đoạn chat cũ sau 30 ngày để giảm dung lượng lưu trữ.
- **Xử lý đồng bộ đa thiết bị (Multi-device Conflict Resolution):** Đang giả định client đồng bộ đơn luồng tuyến tính.


### Phạm vi triển khai và độ tươi thực tế

Các tier streaming/batch ở trên là phương án kiến trúc, chưa phải dịch vụ đang chạy.
POC `remember()` upsert đồng bộ vào Qdrant in-memory và cập nhật BM25 trong cùng
process. Không có SLA sub-second được kiểm chứng. Hồ sơ và velocity đến từ
Parquet tổng hợp của NB4, sau đó `feast materialize-incremental` ghi vào SQLite;
chưa có Kafka/Flink hoặc Feast Push Source và `remember()` không cập nhật velocity.
Nếu registry chưa tồn tại, demo dùng giá trị mặc định và in rõ nguồn dữ liệu.
Nếu lookup lỗi, code cảnh báo thay vì xem giá trị mặc định là dữ liệu thật.
TTL của feature view ràng buộc dữ liệu cho historical/materialization; không nên
coi TTL này là cam kết mọi online value tự hết hạn đúng thời điểm trên SQLite.
Một triển khai thực cần timestamp độ tươi và kiểm tra stale value khi ghép context.
PIT join trong NB4/NB8 giữ nguồn feature không muộn hơn thời điểm của entity;
đó là yêu cầu bắt buộc khi huấn luyện, kể cả khi serving dùng giá trị mới nhất.

BM25 được xây lại sau mỗi ghi nhớ, phù hợp vài ghi chú trong demo nhưng không
phù hợp hàng triệu bản ghi. Qdrant local quét chính xác, không có HNSW production.
Dữ liệu mất khi process kết thúc; lớp agent này chỉ dùng một instance trong demo.
Người gọi truyền `user_id`, chưa có authentication binding. Demo kiểm tra hai user
không nhìn thấy text của nhau, nhưng chưa chứng minh chống giả mạo danh tính.
`recall()` chỉ trả context; không gọi LLM sinh câu trả lời, không tự đề xuất tài liệu
ngoài các ghi chú đã lưu. Muốn nâng cấp model đa ngữ phải re-index, đo lại golden
set và kiểm tra latency; không mặc định chất lượng tăng ở mọi query.
