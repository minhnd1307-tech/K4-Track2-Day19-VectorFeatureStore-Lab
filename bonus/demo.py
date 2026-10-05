"""Demo script running 5 queries with HybridMemoryAgent (Bonus Challenge).

Prints assembled context for:
1. Simple episodic recall (Kubernetes notes)
2. Profile-guided recommendation (topic_affinity)
3. Fresh activity / recent velocity
4. Paraphrase query (vector semantic hit)
5. Mixed query (hybrid episodic search + stable profile)

Exits 0 upon successful completion.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bonus.agent import HybridMemoryAgent


def main() -> int:
    print("=" * 70)
    print("Bonus Challenge: HybridMemoryAgent 5-Query Demo")
    print("=" * 70)

    agent = HybridMemoryAgent()
    print("Profile source:", "Feast online store" if agent._fs is not None else "demo defaults (run NB4 for real features)")

    # Seed episodic memory for user u_001
    sample_notes = [
        "Kubernetes deployment ghi chú: Cần cấu hình Horizontal Pod Autoscaler (HPA) "
        "kết hợp Prometheus custom metrics để scale theo số lượng request.",
        "Kiến trúc Cloud Security: Quản lý secret bằng HashiCorp Vault và tuân thủ "
        "mô hình Zero Trust Network Access (ZTNA) cho toàn bộ VPC peering.",
        "Kinh nghiệm DevOps: Pipeline CI/CD trên GitHub Actions tự động build multi-arch "
        "Docker image và scan lỗ hổng bằng Trivy trước khi deploy vào staging.",
        "Tối ưu chi phí hạ tầng AWS: Sử dụng Spot Instances cho worker node kết hợp "
        "Karpenter để tự động co giãn cụm compute linh hoạt theo tải.",
        "Cơ sở dữ liệu phân tán: Sử dụng PostgreSQL read replicas và PgBouncer "
        "để tối ưu connection pooling cho high concurrency.",
    ]

    print("\n1. Ingesting user notes into episodic memory (Vector Store)...")
    for note in sample_notes:
        agent.remember(note, user_id="u_001")
    private_marker = "GLOBEX_PRIVATE_NOTE_92841"
    agent.remember(private_marker + " Kubernetes secret", user_id="u_002")
    assert private_marker not in agent.recall("Kubernetes secret", user_id="u_001", top_k=10)
    assert private_marker in agent.recall("Kubernetes secret", user_id="u_002")
    assert "No relevant episodic memory" in agent.recall("Kubernetes", user_id="unknown")
    print("User isolation self-check: PASS")
    print(f"   Indexed {len(sample_notes)} notes for user u_001.\n")

    queries = [
        ("Query 1 [Simple episodic recall]", "Tôi đã đọc gì về Kubernetes?"),
        ("Query 2 [Profile-guided context]", "Recommend đọc gì tiếp"),
        ("Query 3 [Fresh activity velocity]", "Tôi đang quan tâm gì gần đây?"),
        ("Query 4 [Paraphrase query]", "Tài liệu về tự động mở rộng hạ tầng?"),
        ("Query 5 [Mixed query - hybrid + profile]", "Cho tôi summary cloud security"),
    ]

    for label, q in queries:
        print("-" * 70)
        print(f"{label}")
        print(f"Query: {q!r}")
        context = agent.recall(q, user_id="u_001", top_k=2)
        if label.startswith("Query 1"):
            assert "Horizontal Pod Autoscaler" in context, "Kubernetes lookup must retrieve the saved Kubernetes note"
        print("Assembled Context:")
        print(context)
        print()

    print("=" * 70)
    print("DEMO SUCCESS: All 5 queries completed successfully. Exit 0.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
