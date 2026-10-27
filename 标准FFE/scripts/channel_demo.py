"""绘制教学用信道与 FFE 卷积示意，不代表实际链路测量。"""

from __future__ import annotations

import csv
from pathlib import Path

from ffe import DEFAULT_COEFFS


# 两个有限离散序列级联时，对应其线性卷积。
def convolution(a: list[float], b: list[float]) -> list[float]:
    output: list[float] = []
    for out_index in range(len(a) + len(b) - 1):
        total = 0.0
        for a_index, a_value in enumerate(a):
            b_index = out_index - a_index
            if 0 <= b_index < len(b):
                total += a_value * b[b_index]
        output.append(total)
    return output


# 用主游标能量归一化其余游标能量，仅作本示例内的对比指标。
def isi_ratio(taps: list[float], main: int) -> float:
    main_energy = taps[main] ** 2
    other_energy = 0.0
    for index, value in enumerate(taps):
        if index != main:
            other_energy += value * value
    return other_energy / main_energy


def write_demo(build: Path) -> tuple[float, float]:

    # 这是用于说明卷积效果的假设信道，不用于拟合或验证硬件系数。
    channel = [0.1, 0.5, 0.1]
    equalizer = [coefficient / 64 for coefficient in DEFAULT_COEFFS]
    combined = convolution(channel, equalizer)
    before = isi_ratio(channel, 1)
    after = isi_ratio(combined, 3)

    csv_path = build / "channel.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["symbol_offset", "channel", "channel_then_ffe"])
        for index in range(len(combined)):
            channel_value = channel[index] if index < len(channel) else 0
            writer.writerow([index, channel_value, combined[index]])

    width, height = 900, 340
    rows = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
            '<rect width="900" height="340" fill="#101820"/>',
            '<style>text{font:15px sans-serif;fill:#dbe6ee}</style>',
            '<text x="30" y="30" font-size="21">Toy channel impulse response</text>',
            '<text x="30" y="55">Blue: channel (main at 1)   Orange: channel + FFE (main at 3)</text>',
            f'<text x="30" y="80">Off-main/main energy ratio: {before:.4f} → {after:.4f}</text>',
            '<line x1="50" y1="255" x2="870" y2="255" stroke="#8fa1ac"/>']
    for index in range(len(combined)):
        x_position = 95 + index * 115
        bar_values = [(channel[index] if index < len(channel) else 0, -18, "#51a7f9"),
                      (combined[index], 18, "#ff9d48")]
        for value, x_offset, color in bar_values:
            y_position = 255 - value * 220
            rows.append(f'<line x1="{x_position+x_offset}" y1="255" x2="{x_position+x_offset}" y2="{y_position:.2f}" stroke="{color}" stroke-width="13"/>')
        rows.append(f'<text x="{x_position-5}" y="285">{index}</text>')
    rows.append("</svg>")
    svg_path = build / "channel.svg"
    svg_path.write_text("\n".join(rows), encoding="utf-8")
    return before, after
