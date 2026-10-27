"""生成可编辑的 draw.io 架构图和对应 SVG 导出。"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

COLORS = {
    "blue": ("#E8F1FB", "#4C78A8"),
    "teal": ("#E5F5F2", "#2A8C82"),
    "orange": ("#FFF1DF", "#D68A24"),
    "purple": ("#F0EAFE", "#8064A2"),
    "gray": ("#F1F3F5", "#77818B"),
    "red": ("#FDECEC", "#C65A5A"),
}


class Page:
    """在 draw.io mxGraph XML 中放置卡片、標題和带箭头连线。"""

    def __init__(self, name: str, width: int, height: int, subtitle: str):
        self.name = name
        self.width = width
        self.height = height
        self.cells: list[ET.Element] = []
        self.next_id = 2
        self.card("标题", name, 35, 18, width - 70, 44, "title")
        self.card("副标题", subtitle, 40, 65, width - 80, 38, "note")

    def card(self, key: str, text: str, x: int, y: int, w: int, h: int, kind: str = "blue") -> str:
        cell_id = str(self.next_id)
        self.next_id += 1
        if kind == "title":
            style = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontFamily=PingFang SC;fontSize=26;fontStyle=1;fontColor=#18324A;"
        elif kind == "note":
            style = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontFamily=PingFang SC;fontSize=15;fontColor=#52616F;"
        else:
            fill, stroke = COLORS.get(kind, COLORS["blue"])
            style = ("rounded=1;whiteSpace=wrap;html=1;arcSize=12;shadow=0;" 
                     f"fillColor={fill};strokeColor={stroke};strokeWidth=2;" 
                     "fontFamily=PingFang SC;fontSize=15;fontColor=#203040;align=center;verticalAlign=middle;spacing=10;")
        cell = ET.Element("mxCell", {"id": cell_id, "value": text, "style": style, "vertex": "1", "parent": "1"})
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"})
        self.cells.append(cell)
        return cell_id

    def edge(self, source: str, target: str, label: str = "", color: str = "#607D8B", dashed: bool = False, entry_x: float | None = None) -> None:
        cell_id = str(self.next_id)
        self.next_id += 1
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;" 
                 f"strokeColor={color};strokeWidth=2;endArrow=block;endFill=1;fontFamily=PingFang SC;fontSize=13;fontColor=#37474F;")
        if dashed:
            style += "dashed=1;dashPattern=6 4;"
        if entry_x is not None:
            style += f"entryX={entry_x:.3f};entryY=0;entryDx=0;entryDy=0;"
        cell = ET.Element("mxCell", {"id": cell_id, "value": label, "style": style, "edge": "1", "parent": "1", "source": source, "target": target})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        self.cells.append(cell)

    def xml(self) -> ET.Element:
        diagram = ET.Element("diagram", {"id": self.name.replace(" ", "_"), "name": self.name})
        model = ET.SubElement(diagram, "mxGraphModel", {"dx": str(self.width), "dy": str(self.height), "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(self.width), "pageHeight": str(self.height), "math": "0", "shadow": "0"})
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
        root.extend(self.cells)
        return diagram


def rtl_datapath() -> Page:
    p = Page("RTL 总体框图", 2180, 820, "直接型 5-tap FIR：组合乘加与量化在输入路径上；历史样本和输出只在有效上升沿更新。")
    control = p.card("控制", "控制：clk / rst_n / in_valid\n异步复位清空历史和输出；in_valid 控制状态推进", 40, 125, 2080, 72, "gray")
    xin = p.card("当前样本", "x_in\n当前样本", 45, 280, 150, 84, "blue")
    regs = []
    for i, label in enumerate(("d1", "d2", "d3", "d4")):
        regs.append(p.card(label, f"{label} 寄存器\n最近第 {i+1} 个历史有效样本", 285 + i * 215, 260, 165, 88, "teal"))
    p.edge(xin, regs[0])
    for a, b in zip(regs, regs[1:]):
        p.edge(a, b)

    mults = []
    for i, (label, x) in enumerate(zip(("x_in", "d1", "d2", "d3", "d4"), (55, 270, 485, 700, 915))):
        m = p.card(f"乘法器 {i}", f"抽头 {i}\n{label} × C{i}\nC{i} = ({(-4, -12, 64, -16, 4)[i]})", x, 465, 175, 102, "orange")
        mults.append(m)
    p.edge(xin, mults[0], "tap 0")
    for i in range(4):
        p.edge(regs[i], mults[i+1], f"tap {i+1}")

    products = p.card("乘积总线", "5 路独立乘积 p0..p4\n各路保留完整 16 位 signed 结果", 55, 620, 1035, 76, "purple")
    for i, m in enumerate(mults):
        center = 142.5 + i * 215
        p.edge(m, products, f"p{i}", entry_x=(center - 55) / 1035)
    add = p.card("加法树", "符号扩展至 19 位\n五路求和得到 acc", 1150, 450, 190, 130, "purple")
    shift = p.card("定点缩放", "算术右移 FRAC=6\n负数保留符号\nshifted", 1375, 465, 190, 100, "blue")
    sat = p.card("饱和器", "限制至 signed 8-bit\n[-128, 127]\nquantized", 1615, 465, 190, 100, "red")
    yreg = p.card("输出寄存器", "posedge clk 且 in_valid=1\n锁存 quantized\ny_out / out_valid", 1860, 450, 260, 130, "teal")
    p.edge(products, add, "p0..p4")
    p.edge(add, shift)
    p.edge(shift, sat)
    p.edge(sat, yreg)
    p.card("时序提示", "一个有效上升沿同时：\n① y_out 锁存由沿前 x_in、d1..d4 算出的结果；② d1..d4 前移；③ out_valid <= in_valid。\n气泡时历史与 y_out 保持，out_valid 拉低。", 45, 720, 2075, 78, "gray")
    return p


def rtl_cycle() -> Page:
    p = Page("RTL 每拍处理", 1760, 900, "要点：乘加不是多拍流水。输入在上升沿被接收，输出在同一上升沿之后更新；持续有效时每拍一个样本。")
    before = p.card("沿前组合路径", "本周期稳定的 x_in 与 d1..d4\n→ 5 个常数乘法\n→ 19 位累加 acc\n→ 算术右移 6 位\n→ 饱和器得到 quantized", 70, 165, 455, 250, "blue")
    edge = p.card("采样时刻", "posedge clk\n检查 rst_n\n\n若 rst_n=0：异步清零状态\n否则：out_valid <= in_valid", 645, 190, 400, 200, "purple")
    decision = p.card("有效？", "in_valid == 1", 800, 455, 220, 110, "orange")
    accepted = p.card("有效样本", "同一个上升沿：\ny_out <= quantized\nd1 <= x_in\nd2 <= 旧 d1\nd3 <= 旧 d2\nd4 <= 旧 d3\nout_valid = 1", 1190, 170, 450, 265, "teal")
    bubble = p.card("气泡周期", "同一个上升沿：\n历史寄存器保持\ny_out 保持\nout_valid = 0\n组合 acc 仍可随输入变化", 1190, 520, 450, 230, "gray")
    p.edge(before, edge, "quantized 在沿前就绪")
    p.edge(edge, decision, "时钟沿")
    p.edge(decision, accepted, "是")
    p.edge(decision, bubble, "否")
    p.card("复位", "rst_n 为低时不等待时钟：立即清零 d1..d4、y_out、out_valid。释放复位后，历史零值等价于有效输入序列前补零。", 70, 600, 970, 150, "red")
    p.card("时序与吞吐", "接受输入的时钟沿后输出寄存器立即更新（不额外等待一个完整周期）；out_valid 与该结果对齐。无 ready/反压端口；in_valid=0 是暂停状态更新的气泡。", 70, 785, 1570, 72, "blue")
    return p


def python_functions() -> Page:
    p = Page("Python 函数职责图", 2340, 1180, "按源码真实函数分组；FFE.step 是位精确模型核心，其它模块负责向量生成、RTL 回归、作图和教学信道卷积。")
    # ffe.py
    p.card("ffe.py", "参考模型：ffe.py", 35, 120, 720, 46, "blue")
    helpers = p.card("纯函数", "signed_range(width)：计算有符号范围\narithmetic_shift(value, amount)：模拟 RTL 算术右移\nsaturate(value, width)：饱和限幅", 55, 190, 680, 145, "blue")
    init = p.card("初始化", "FFE.__post_init__()：检查 5 个系数及系数位宽，再清零状态\nFFE.accumulator_width：计算乘积累加所需位宽", 55, 355, 680, 110, "teal")
    step = p.card("逐拍核心", "FFE.reset()：history=[0,0,0,0]，output=0\nFFE.step(sample, valid)：组 taps → 乘系数 → 求和 → 右移 → 饱和；valid 时更新 history/output\nFFE.process(samples)：连续有效处理并收集输出", 55, 485, 680, 185, "orange")
    vectors = p.card("向量与命令行", "demo_samples(seed)：确定性生成 296 个输入\nwrite_vectors(path, samples, model)：写 taps / products / acc / y CSV\nmain()：解析 --csv、调用生成器与写出函数", 55, 690, 680, 145, "purple")
    # scripts/run.py
    p.card("run.py", "仿真编排：scripts/run.py", 800, 120, 720, 46, "teal")
    run = p.card("run(args)", "显示并执行子进程命令；cwd 固定在工程根目录，失败即退出。", 820, 190, 680, 85, "teal")
    svg = p.card("make_svg(rows, path)", "把 wave.csv 的输入、Python 期望、RTL 输出和累加器画成波形 SVG。\n内部 x() / yv() / ya() 做坐标映射；poly() 生成曲线点列。", 820, 295, 680, 130, "blue")
    main = p.card("main()", "检查 COUNT 契约 → 生成 CSV/MEM → 编译并运行 Icarus → 检查每拍输出、气泡和 acc → 生成波形与信道图。", 820, 445, 680, 135, "orange")
    p.card("main 调用链", "demo_samples / write_vectors / FFE.step\n→ iverilog + vvp 执行 tb_ffe\n→ 检查 wave.csv 与 ffe.vcd\n→ make_svg + write_demo", 820, 600, 680, 145, "purple")
    # channel_demo.py and tests
    p.card("channel_demo.py 与测试", "教学卷积：scripts/channel_demo.py", 1565, 120, 730, 46, "purple")
    conv = p.card("convolution(a, b)", "计算两个有限离散序列的线性卷积；说明信道与均衡器级联响应。", 1585, 190, 690, 90, "blue")
    ratio = p.card("isi_ratio(taps, main)", "计算非主抽头能量 / 主抽头能量；只用于教学示例内对比。", 1585, 300, 690, 90, "teal")
    demo = p.card("write_demo(build)", "设置假设信道 → 卷积 → 计算前后比例 → 输出 channel.csv 和 channel.svg。", 1585, 410, 690, 120, "orange")
    tests = p.card("测试函数：tb/test_model.py", "test_rtl_default_parameters_match_reference：核对 RTL 参数/系数\ntest_impulse_response：核对冲激响应\ntest_against_independent_convolution：独立卷积交叉验证\ntest_invalid_cycle_matches_rtl_hold_behavior：核对气泡保持\ntest_reset_and_bounds：核对复位、位宽边界与饱和\n脚本入口调用 unittest.main()", 1585, 560, 690, 200, "red")
    p.card("怎么阅读 / 图表工具", "先看 FFE.step 理解单个采样怎样被均衡；再看 run.py/main 理解 Python 如何驱动 RTL 回归；最后看 channel_demo 的连续信道卷积。create_diagrams.py：Page.__init__ 建页，card/edge 放图元，xml 序列化；四个 builder 组图，locate_drawio/main 生成 draw.io 并导出 SVG。完整软硬件调用关系见下一页。", 55, 890, 2220, 130, "gray")
    return p


def system_flow() -> Page:
    p = Page("软硬件整体系统图", 2220, 1040, "Python 负责参考计算和构造回归；SystemVerilog 实现相同定点公式；testbench 在每个有效时钟沿对照并导出可查看的证据。")
    py = p.card("Python 输入", "ffe.py\ndemo_samples()\n确定性样本与边界用例", 45, 185, 290, 125, "blue")
    model = p.card("参考运算", "FFE.step()\ntaps → products → acc\n右移 → 饱和 → expected y", 390, 185, 330, 140, "orange")
    csv = p.card("人工检查表", "write_vectors()\nbuild/vectors.csv\n逐样本展示中间量", 790, 130, 300, 125, "teal")
    mem = p.card("仿真激励", "run.py\nbuild/vectors.mem\n每行：输入 x + 期望 y", 790, 300, 300, 125, "teal")
    tb = p.card("SystemVerilog TB", "tb_ffe.sv\n读取 MEM；驱动 x_in/in_valid\n检查 y_out、历史和气泡", 1160, 205, 330, 160, "purple")
    rtl = p.card("被测硬件", "rtl/ffe.sv\n五路常数乘法 → 累加\n缩放 → 饱和 → 输出寄存器", 1570, 205, 350, 160, "orange")
    wave = p.card("仿真记录", "build/wave.csv\n每周期记录 valid、x、expected、y、acc\nbuild/ffe.vcd\n关键硬件信号波形", 1570, 445, 420, 175, "blue")
    check = p.card("逐拍核对", "scripts/run.py\n有效周期：RTL y == Python expected\n所有周期：状态输出/组合 acc 符合模型\n任一不符即断言失败", 1040, 465, 430, 160, "red")
    charts = p.card("可视化产物", "make_svg() → build/wave.svg\nchannel_demo.write_demo()\n→ build/channel.csv / channel.svg\n测试证据与教学示意分开", 500, 485, 450, 150, "teal")
    tests = p.card("单元测试", "tb/test_model.py\n独立公式与系数契约\npython3 -m unittest discover -s tb -p 'test_*.py'", 45, 485, 390, 150, "gray")
    p.edge(py, model)
    p.edge(model, csv)
    p.edge(model, mem)
    p.edge(mem, tb)
    p.edge(tb, rtl)
    p.edge(tb, wave)
    p.edge(wave, check)
    p.edge(model, check)
    p.edge(check, charts)
    p.edge(model, tests)
    p.card("运行关系", "在工程根目录执行：python3 -m unittest discover -s tb -p 'test_*.py'；随后 python3 scripts/run.py。run.py 会先准备 Python 数据，再调用 iverilog/vvp，验证 RTL 与参考模型，最后写出波形和教学信道图。", 45, 760, 1940, 115, "gray")
    p.card("重要边界", "VCD 是仿真信号记录；SVG 是由 CSV 绘制的静态曲线。波形外观用于观察，数值正确性由 testbench 断言和 Python 逐周期比较负责。", 45, 905, 1940, 75, "red")
    return p


def locate_drawio() -> str:
    executable = shutil.which("drawio") or shutil.which("draw.io")
    if executable:
        return executable
    mac_app = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")
    if mac_app.exists():
        return str(mac_app)
    raise FileNotFoundError("未找到 draw.io 命令行；请安装 diagrams.net 桌面版后重试。")


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    pages = [rtl_datapath(), rtl_cycle(), python_functions(), system_flow()]
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "modified": "2026-10-27T00:00:00.000Z", "agent": "FFE diagram generator", "version": "24.7.17", "type": "device"})
    for page in pages:
        mxfile.append(page.xml())
    ET.indent(mxfile, space="  ")
    source = DOCS / "ffe_design.drawio"
    ET.ElementTree(mxfile).write(source, encoding="utf-8", xml_declaration=True)

    drawio = locate_drawio()
    names = ["ffe_architecture.svg", "rtl_cycle.svg", "python_functions.svg", "system_overview.svg"]
    for index, name in enumerate(names, start=1):
        subprocess.run([drawio, "--export", "--format", "svg", "--embed-svg-fonts", "false",
                        "--page-index", str(index), "--output", str(DOCS / name), str(source)], check=True)
    print(f"已生成 {source.relative_to(ROOT)} 和 {len(names)} 张 draw.io SVG 图。")


if __name__ == "__main__":
    main()
