`timescale 1ns/1ps
// 从 Python 生成的向量读取输入和期望输出，并逐周期检查 RTL。
module tb_ffe;
    // 数量由 scripts/run.py 与 Python 激励长度交叉检查。
    localparam int COUNT = 296;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0;
    logic in_valid = 0;
    logic signed [7:0] x_in = 0;
    wire out_valid;
    wire signed [7:0] y_out;
    logic [15:0] vectors [0:COUNT-1];
    integer log_file;
    integer i;
    integer cycle = 0;

    ffe dut (.*);

    // 在下降沿驱动、上升沿采样，避免 testbench 与 DUT 发生竞态。
    task automatic drive_and_check(input bit valid_i, input logic signed [7:0] x_i,
                                   input logic signed [7:0] expected_i);
        logic signed [7:0] prior_y, prior_d1, prior_d2, prior_d3, prior_d4;
        begin
            @(negedge clk);
            prior_y = y_out;
            prior_d1 = dut.d1;
            prior_d2 = dut.d2;
            prior_d3 = dut.d3;
            prior_d4 = dut.d4;
            in_valid = valid_i;
            x_in = x_i;
            @(posedge clk);
            #1;
            cycle = cycle + 1;
            if (out_valid !== valid_i) $fatal(1, "valid mismatch cycle %0d", cycle);
            if (valid_i && y_out !== expected_i)
                $fatal(1, "cycle %0d x=%0d expected=%0d actual=%0d",
                       cycle, x_i, expected_i, y_out);
            // 有效样本推进延迟线；气泡必须同时保持输出和历史。
            if (valid_i) begin
                if (dut.d1 !== x_i || dut.d2 !== prior_d1 ||
                    dut.d3 !== prior_d2 || dut.d4 !== prior_d3)
                    $fatal(1, "history did not advance at cycle %0d", cycle);
            end else if (y_out !== prior_y || dut.d1 !== prior_d1 ||
                         dut.d2 !== prior_d2 || dut.d3 !== prior_d3 ||
                         dut.d4 !== prior_d4) begin
                $fatal(1, "invalid cycle changed output/history at cycle %0d", cycle);
            end
            $fdisplay(log_file, "%0d,%0d,%0d,%0d,%0d,%0d", cycle, valid_i,
                      x_i, valid_i ? expected_i : y_out, y_out, dut.acc);
        end
    endtask

    // 生成 VCD/CSV、验证异步复位，再运行向量与周期性无效气泡。
    initial begin
        $readmemh("build/vectors.mem", vectors);
        $dumpfile("build/ffe.vcd");

        // 默认只记录八个关键量，兼顾波形查看器的信号数量限制。
        $dumpvars(0, tb_ffe.clk, tb_ffe.in_valid, tb_ffe.x_in,
                  tb_ffe.dut.d1, tb_ffe.dut.d2, tb_ffe.dut.acc,
                  tb_ffe.out_valid, tb_ffe.y_out);
        log_file = $fopen("build/wave.csv", "w");
        $fdisplay(log_file, "cycle,valid,x,expected,y,acc");
        repeat (3) @(negedge clk);
        if (out_valid !== 1'b0 || y_out !== 8'sd0 || dut.d1 !== 8'sd0 ||
            dut.d2 !== 8'sd0 || dut.d3 !== 8'sd0 || dut.d4 !== 8'sd0)
            $fatal(1, "asynchronous reset did not clear output/history");
        rst_n = 1;
        for (i = 0; i < COUNT; i = i + 1) begin
            if (i > 0 && i % 7 == 0)
                drive_and_check(0, 0, 0);
            drive_and_check(1, $signed(vectors[i][15:8]), $signed(vectors[i][7:0]));
        end
        drive_and_check(0, 0, 0);
        $fclose(log_file);
        $display("PASS: %0d Python reference vectors, bubbles and reset", COUNT);
        $finish;
    end
endmodule
