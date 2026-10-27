# FFE 工程

本仓库收录前馈均衡器（Feed-Forward Equalizer，FFE）的教学与验证工程。

## 标准 FFE

完整工程位于 [`标准FFE/`](标准FFE/)，包括：

- FFE 原理说明、结构图和 PPA 架构分析；
- Python 定点参考模型及教学信道示例；
- 与 Python 模型逐周期对照的 SystemVerilog RTL 和 testbench；
- 仿真脚本、测试向量以及 VCD/SVG 波形示例。

从[工程 README](标准FFE/README.md)开始了解环境要求、运行方法和 Python/RTL 对应关系。

```bash
cd 标准FFE
python3 -m unittest discover -s tb -p 'test_*.py'
python3 scripts/run.py
```

上述命令会运行 Python 单元测试，并执行 RTL 仿真及逐周期模型对照。生成结果保存在 `标准FFE/build/`。
