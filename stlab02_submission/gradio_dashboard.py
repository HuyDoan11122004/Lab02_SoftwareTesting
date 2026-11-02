"""Build a local dashboard from reports/test_execution.csv; never launch on import."""
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("GRADIO_TEMP_DIR", str(ROOT / "reports" / ".gradio"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "reports" / ".matplotlib"))
import gradio as gr
import pandas as pd
from matplotlib.figure import Figure


def dashboard_view(requirement="ALL", status="ALL"):
    # Read each time to avoid stale reports after rerun.
    frame = pd.read_csv(ROOT / "reports" / "test_execution.csv", keep_default_na=False)
    if requirement != "ALL":
        frame = frame.loc[frame.requirement_id == requirement]
    if status != "ALL":
        frame = frame.loc[frame.execution_status == status]
    counts = frame.execution_status.value_counts().reindex(["PASS", "FAIL", "BLOCKED"], fill_value=0)
    figure = Figure(figsize=(6, 4), layout="constrained")
    axes = figure.subplots()
    bars = axes.bar(counts.index, counts.values, color=["#15803d", "#dc2626", "#b45309"])
    axes.bar_label(bars, padding=3)
    axes.set_ylim(0, max(2, int(counts.max()) + 2))
    axes.set_ylabel("Test cases")
    axes.set_title("Kết quả theo bộ lọc")
    columns = ["test_case_id", "requirement_id", "condition_id", "scenario_id", "execution_status",
               "expected_json", "actual_result", "execution_time_ms", "evidence_reference"]
    text = f"Hiển thị: {len(frame)} | PASS: {counts['PASS']} | FAIL: {counts['FAIL']} | BLOCKED: {counts['BLOCKED']}"
    return figure, frame[columns], text


def build_dashboard():
    frame = pd.read_csv(ROOT / "reports" / "test_execution.csv", keep_default_na=False)
    with gr.Blocks(title="EduCommerce Test Dashboard") as demo:
        gr.Markdown("# EduCommerce — Kết quả kiểm thử")
        gr.Markdown("Pass rate toàn bộ dùng mọi dòng CSV làm mẫu số; BLOCKED là ca chưa thực thi. Bộ lọc chỉ thay đổi phần hiển thị.")
        with gr.Row():
            requirement = gr.Dropdown(["ALL"] + sorted(frame.requirement_id.unique().tolist()), value="ALL", label="Requirement")
            status = gr.Dropdown(["ALL", "PASS", "FAIL", "BLOCKED"], value="ALL", label="Status")
        status_line = gr.Markdown()
        with gr.Row(equal_height=True):
            with gr.Column(scale=1, min_width=300):
                chart = gr.Plot(label="Biểu đồ kết quả")
            with gr.Column(scale=2, min_width=420):
                table = gr.Dataframe(label="Chi tiết thực thi", interactive=False, wrap=True)
        gr.File(value=str(ROOT / "reports" / "test_report.xlsx"), label="Báo cáo Excel")
        for dropdown in (requirement, status):
            dropdown.change(dashboard_view, inputs=[requirement, status], outputs=[chart, table, status_line])
        demo.load(dashboard_view, inputs=[requirement, status], outputs=[chart, table, status_line])
    return demo


if __name__ == "__main__":
    # Build check only. No local server, share link, or browser launched.
    dashboard = build_dashboard()
    print(f"Dashboard build OK: {type(dashboard).__name__}; share=False; server not started")
