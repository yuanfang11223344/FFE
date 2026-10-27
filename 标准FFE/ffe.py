"""五抽头定点前馈均衡器（FFE）的 Python 位精确参考模型。"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

# 系数为整数编码，实际值等于该整数除以 2**frac_bits。
DEFAULT_COEFFS = (-4, -12, 64, -16, 4)


def signed_range(width: int) -> tuple[int, int]:
    """返回 width 位二进制补码可表示的最小值和最大值。"""
    if width < 1:
        raise ValueError("width must be positive")
    return -(1 << (width - 1)), (1 << (width - 1)) - 1


def arithmetic_shift(value: int, amount: int) -> int:
    """模拟 RTL 有符号算术右移；负数按向负无穷取整。"""
    if amount < 0:
        raise ValueError("shift amount must be non-negative")
    return value >> amount


def saturate(value: int, width: int) -> int:
    """将整数限制在指定宽度的有符号范围内。"""
    low, high = signed_range(width)
    return min(max(value, low), high)


@dataclass
class FFE:
    """五抽头直接型 FFE；step() 对应 RTL 的一次时钟采样。"""

    data_width: int = 8
    coeff_width: int = 8
    frac_bits: int = 6
    coeffs: tuple[int, ...] = DEFAULT_COEFFS
    history: list[int] = field(default_factory=list)
    output: int = 0

    def __post_init__(self) -> None:
        if len(self.coeffs) != 5:
            raise ValueError("this FFE implementation requires exactly five coefficients")
        lo, hi = signed_range(self.coeff_width)
        if any(c < lo or c > hi for c in self.coeffs):
            raise ValueError("coefficient is outside the configured signed range")
        self.reset()

    @property
    def accumulator_width(self) -> int:
        """与 RTL 一样为五个乘积保留保护位。"""
        return self.data_width + self.coeff_width + 3

    def reset(self) -> None:
        """清空四个历史样本。"""
        self.history = [0, 0, 0, 0]
        self.output = 0

    def step(self, sample: int, valid: bool = True) -> dict[str, int | bool | list[int]]:
        """处理一个时钟周期；valid=False 时历史和输出均保持不变。"""
        data_min, data_max = signed_range(self.data_width)
        if sample < data_min or sample > data_max:
            raise ValueError(f"sample {sample} is outside [{data_min}, {data_max}]")
        # RTL 的乘加是组合逻辑：即使 valid 为低，acc 仍随 x_in 和历史值变化。
        # taps 顺序与 RTL 一致：当前输入在前，后面是由近及远的历史样本。
        taps = [sample, *self.history]
        products = [x * c for x, c in zip(taps, self.coeffs)]
        # 乘积和累加期间不截位，量化只发生在移位与饱和阶段。
        acc = sum(products)
        shifted = arithmetic_shift(acc, self.frac_bits)
        quantized = saturate(shifted, self.data_width)
        if valid:
            # 只有有效传输才推进历史并更新输出寄存器。
            self.history = [sample, *self.history[:3]]
            self.output = quantized
        return {"valid": valid, "x": sample, "taps": taps, "products": products,
                "acc": acc, "shifted": shifted, "y": self.output}

    def process(self, samples: list[int]) -> list[int]:
        """连续处理一组有效样本并返回输出。"""
        return [int(self.step(sample)["y"]) for sample in samples]


# 有向边界样本覆盖饱和与符号，再用固定随机种子保证可复现。
def demo_samples(seed: int = 20261027) -> list[int]:
    """生成与 testbench COUNT=296 对应的确定性输入：边界、随机和饱和用例。"""
    directed = [-128, 127, 0, 64, -64, 1, -1, 127, -128, 32,
                -32, 96, -96, 16, -16, 80, -80, 8, -8, 0]
    rng = random.Random(seed)
    random_part = [rng.randint(-128, 127) for _ in range(256)]
    ending = [127, 127, 127, 127, 127, -128, -128, -128, -128, -128,
              0, 0, 0, 0, 0, 64, 0, 0, 0, 0]
    return directed + random_part + ending


def write_vectors(path: Path, samples: list[int], model: FFE) -> None:
    """输出便于人工核对的逐样本 CSV，包含 tap、乘积、累加和输出。"""
    model.reset()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["index", "x", "taps", "products", "acc", "shifted", "y"])
        for index, sample in enumerate(samples):
            result = model.step(sample)
            writer.writerow([index, sample, " ".join(map(str, result["taps"])),
                             " ".join(map(str, result["products"])), result["acc"],
                             result["shifted"], result["y"]])


def main() -> None:
    parser = argparse.ArgumentParser(description="运行五抽头定点 FFE Python 参考模型")
    parser.add_argument("--csv", type=Path, default=Path("build/python_vectors.csv"))
    args = parser.parse_args()
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    samples = demo_samples()
    write_vectors(args.csv, samples, FFE())
    print(f"已生成 {len(samples)} 个样本：{args.csv}")


if __name__ == "__main__":
    main()
