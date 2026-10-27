
// 五抽头直接型 FFE：系数采用 Q 格式，输入历史只随有效样本推进。
module ffe #(
    parameter int DATA_W = 8,
    parameter int COEFF_W = 8,
    parameter int FRAC = 6,
    parameter signed [COEFF_W-1:0] C0 = -4,
    parameter signed [COEFF_W-1:0] C1 = -12,
    parameter signed [COEFF_W-1:0] C2 = 64,
    parameter signed [COEFF_W-1:0] C3 = -16,
    parameter signed [COEFF_W-1:0] C4 = 4
) (
    input  logic clk,
    input  logic rst_n,
    input  logic in_valid,
    input  logic signed [DATA_W-1:0] x_in,
    output logic out_valid,
    output logic signed [DATA_W-1:0] y_out
);
    // 乘积先完整保留，再用保护位累加，最后缩放并饱和到输出位宽。
    localparam int TAPS = 5;
    localparam int PROD_W = DATA_W + COEFF_W;
    localparam int ACC_W = PROD_W + $clog2(TAPS);
    logic signed [DATA_W-1:0] d1, d2, d3, d4;
    logic signed [PROD_W-1:0] p0, p1, p2, p3, p4;
    logic signed [ACC_W-1:0] acc;
    logic signed [ACC_W-1:0] shifted;
    logic signed [ACC_W-1:0] max_out, min_out;
    logic signed [DATA_W-1:0] quantized;


    // tap0 为当前输入，d1 到 d4 依次代表更早的有效样本。
    assign p0 = $signed(x_in) * C0;
    assign p1 = $signed(d1)   * C1;
    assign p2 = $signed(d2)   * C2;
    assign p3 = $signed(d3)   * C3;
    assign p4 = $signed(d4)   * C4;

    // 大致处理思路：当前输入与四个历史样本分别乘以对应系数，得到五个乘积；
    // 将乘积符号扩展后累加，右移 FRAC 位恢复定点整数，再按输出位宽饱和；
    // 最终结果由下方时序逻辑在 in_valid 有效的时钟沿锁存到 y_out。
    // 这里的组合运算不插入寄存器，输入或历史样本变化时会重新计算。
    always_comb begin
        // 每个乘积从 PROD_W 符号扩展到 ACC_W，再相加；避免累加时丢失进位或负号。
        acc = {{(ACC_W-PROD_W){p0[PROD_W-1]}}, p0}
            + {{(ACC_W-PROD_W){p1[PROD_W-1]}}, p1}
            + {{(ACC_W-PROD_W){p2[PROD_W-1]}}, p2}
            + {{(ACC_W-PROD_W){p3[PROD_W-1]}}, p3}
            + {{(ACC_W-PROD_W){p4[PROD_W-1]}}, p4};

        // 系数是 FRAC 位小数定点数；算术右移保留符号并移除小数位。
        shifted = acc >>> FRAC;

        // 输出范围为 [-2^(DATA_W-1), 2^(DATA_W-1)-1]，边界先扩展到 ACC_W。
        max_out = ({{(ACC_W-1){1'b0}}, 1'b1} <<< (DATA_W-1)) - 1;
        min_out = -({{(ACC_W-1){1'b0}}, 1'b1} <<< (DATA_W-1));

        // 超上界钳位到最大正数，低于下界钳位到最小负数，避免回绕。
        if (shifted > max_out)
            quantized = {1'b0, {(DATA_W-1){1'b1}}};
        else if (shifted < min_out)
            quantized = {1'b1, {(DATA_W-1){1'b0}}};
        else
            // 只有确认数值可表示后才取低 DATA_W 位，因此这里不会发生溢出回绕。
            quantized = shifted[DATA_W-1:0];
    end

    // 无效周期保持数据状态；out_valid 每周期反映本周期是否接收了样本。
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            d1 <= '0;
            d2 <= '0;
            d3 <= '0;
            d4 <= '0;
            y_out <= '0;
            out_valid <= 1'b0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                d1 <= x_in;
                d2 <= d1;
                d3 <= d2;
                d4 <= d3;
                y_out <= quantized;
            end
        end
    end
endmodule
