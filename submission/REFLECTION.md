# Reflection — Lab 19

**Tên:** Nguyễn Đức Minh

**Cohort:** A20-K4

**Path:** Lite, CPU, bge-small-en-v1.5

Trên 50 golden queries, Precision@10 của BM25 là 77,8%, vector 73,2%, hybrid
78,6%. Với `exact`, BM25 và hybrid cùng đạt 96,7%. Với `mixed`, hybrid đạt
100%, vượt BM25 97,0% và vector 98,5%: RRF kết hợp hai tín hiệu bổ sung nhau.

Điểm đáng chú ý là `paraphrase`: BM25 đạt 33,3%, vector chỉ 24,0%, hybrid
32,0%. Mô hình tiếng Anh mặc định yếu với tiếng Việt; không thể khẳng định
semantic luôn thắng khi diễn đạt lại. Cần đo mô hình đa ngữ trước khi nâng cấp,
và index lại khi đổi model.

Tôi chọn BM25 cho mã lỗi, ID/SKU hoặc ngân sách CPU/latency rất thấp. Tôi chọn
vector khi cần ngữ nghĩa và mô hình đã được kiểm chứng cho ngôn ngữ dữ liệu.
Hybrid phù hợp truy vấn trộn thuật ngữ và ý nghĩa, nhưng không thắng mọi slice.

**Bonus:** Có `bonus/ARCHITECTURE.md`, agent và demo năm truy vấn. Agent ghép
ghi chú với Feast; streaming là thiết kế đề xuất, chưa triển khai trong POC.
