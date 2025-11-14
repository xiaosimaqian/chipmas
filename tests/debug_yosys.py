"""
Yosys调试脚本
"""

from pathlib import Path
import subprocess
import tempfile

# 创建简单测试
test_verilog = """
module test (
    input wire a,
    input wire b,
    output wire c
);

assign c = a & b;

endmodule
"""

# 创建Yosys测试脚本
yosys_script = """
read_verilog test.v
hierarchy -check -top test
proc
"""

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    
    # 写入Verilog文件
    verilog_file = tmpdir / 'test.v'
    with open(verilog_file, 'w') as f:
        f.write(test_verilog)
    
    # 写入Yosys脚本
    script_file = tmpdir / 'test.ys'
    with open(script_file, 'w') as f:
        f.write(yosys_script)
    
    print("测试文件创建：")
    print(f"  Verilog: {verilog_file}")
    print(f"  Script: {script_file}")
    print()
    
    # 运行Yosys
    print("运行Yosys...")
    result = subprocess.run(
        ['yosys', '-s', str(script_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=tmpdir
    )
    
    print(f"\n返回码: {result.returncode}")
    print(f"\n输出:")
    print(result.stdout)
    
    if result.returncode == 0:
        print("\n✓ Yosys基础功能正常！")
    else:
        print("\n✗ Yosys执行失败！")
        print("\n可能的原因：")
        print("1. Verilog语法问题")
        print("2. Yosys命令参数问题")
        print("3. 文件路径问题")

