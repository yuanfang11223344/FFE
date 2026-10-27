"""生成测试向量，运行 RTL 仿真并输出对比图。"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ffe import FFE, demo_samples, write_vectors
from scripts.channel_demo import write_demo


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


# 汇总输入、Python 期望值、RTL 输出与累加器，便于检查波形是否一致。
def make_svg(rows: list[dict[str, str]], path: Path) -> None:
    width, height = 1200, 470
    left, right = 80, 25
    plot_w = width - left - right
    n = len(rows)
    xscale = plot_w / max(n - 1, 1)

    def x(i: int) -> float:
        return left + i * xscale

    def yv(v: int) -> float:
        return 265 - v * 0.72

    def ya(v: int) -> float:
        return 395 - v * 0.006

    def poly(key: str, coordinate: Callable[[int], float]) -> str:
        return " ".join(f"{x(i):.1f},{coordinate(int(row[key])):.1f}" for i, row in enumerate(rows))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101820"/>',
             '<style>text{font:14px sans-serif;fill:#dbe6ee}.axis{stroke:#557080;stroke-width:1}.grid{stroke:#283c49;stroke-width:1}</style>',
             '<text x="80" y="30" font-size="20">FFE: Python expected vs RTL output</text>',
             '<text x="80" y="55">Blue: accepted input   Green: Python   Orange: RTL   Purple: accumulator</text>']
    for value in (-128, -64, 0, 64, 127):
        yy = yv(value)
        parts += [f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}"/>',
                  f'<text x="8" y="{yy+4:.1f}">{value}</text>']
    for i, row in enumerate(rows):
        if row["valid"] == "0":
            xx = x(i)
            parts.append(f'<rect x="{xx-4:.1f}" y="75" width="8" height="365" fill="#606878" opacity=".3"/>')
        if i % 25 == 0 or i == n - 1:
            parts.append(f'<text x="{x(i)-5:.1f}" y="455">{row["cycle"]}</text>')
    traces = [("x", "#51a7f9", yv), ("expected", "#49d69c", yv),
              ("y", "#ff9d48", yv), ("acc", "#b88cff", ya)]
    for key, color, coordinate in traces:
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{poly(key, coordinate)}"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


# 单入口流程：生成向量 → 仿真 → 比较 → 导出波形图。
def main() -> None:
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    vectors = demo_samples()
    tb_source = (ROOT / "tb" / "tb_ffe.sv").read_text(encoding="utf-8")
    # 防止 Python 激励数量与 testbench 循环上限悄悄分叉。
    count_match = re.search(r"localparam\s+int\s+COUNT\s*=\s*(\d+)", tb_source)
    if count_match is None or len(vectors) != int(count_match.group(1)):
        raise ValueError("demo_samples length must match tb_ffe.sv COUNT")
    write_vectors(build / "vectors.csv", vectors, FFE())
    model = FFE()
    with (build / "vectors.mem").open("w", encoding="ascii") as vector_file:
        for sample in vectors:
            y = int(model.step(sample)["y"])
            vector_file.write(f"{sample & 255:02x}{y & 255:02x}\n")
    run("iverilog", "-g2012", "-s", "tb_ffe", "-o", "build/tb_ffe",
        "rtl/ffe.sv", "tb/tb_ffe.sv")
    run("vvp", "build/tb_ffe")
    with (build / "wave.csv").open(newline="", encoding="utf-8") as wave_file:
        rows = list(csv.DictReader(wave_file))
    accepted = [row for row in rows if row["valid"] == "1"]
    assert len(accepted) == len(vectors)
    # 每个有效周期都必须逐笔匹配，气泡周期则由 testbench 检查保持行为。
    assert all(row["expected"] == row["y"] for row in accepted)
    # 再按 CSV 的每个时钟周期驱动模型，检查无效周期的保持输出和组合累加器。
    cycle_model = FFE()
    for row in rows:
        expected_cycle = cycle_model.step(int(row["x"]), valid=row["valid"] == "1")
        assert int(row["y"]) == expected_cycle["y"], f"output mismatch at cycle {row['cycle']}"
        # CSV 在时钟沿后记录 acc；有效沿已推进历史，所以用沿后状态重算组合值。
        post_edge_taps = [int(row["x"]), *cycle_model.history]
        post_edge_acc = sum(x * c for x, c in zip(post_edge_taps, cycle_model.coeffs))
        assert int(row["acc"]) == post_edge_acc, f"accumulator mismatch at cycle {row['cycle']}"
    assert (build / "ffe.vcd").stat().st_size > 1000
    make_svg(rows, build / "wave.svg")
    before, after = write_demo(build)
    print(f"PASS: {len(accepted)} accepted samples; VCD and SVG generated")
    print(f"Toy channel ISI/main energy ratio: {before:.4f} -> {after:.4f}")


if __name__ == "__main__":
    main()
