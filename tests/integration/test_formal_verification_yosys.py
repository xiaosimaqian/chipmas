"""
完整的Formal Verification集成测试（使用真实Yosys）

这个测试会实际运行Yosys来验证等价性
"""

from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.formal_verification import FormalVerifier, verify_hierarchical_transformation


def create_simple_flat_netlist(netlist_path: Path):
    """创建一个简单的平坦网表"""
    netlist_content = """
module adder (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);

assign sum = a + b;

endmodule
"""
    netlist_path.parent.mkdir(parents=True, exist_ok=True)
    with open(netlist_path, 'w') as f:
        f.write(netlist_content)


def create_equivalent_hierarchical_netlists(output_dir: Path):
    """创建等价的层级化网表（正确案例）"""
    
    # 子模块1: 低位加法
    partition_0_content = """
module partition_0 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [3:0] sum_low,
    output wire carry
);

assign {carry, sum_low} = a + b;

endmodule
"""
    
    # 顶层: 使用子模块
    top_content = """
module adder (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);

wire [3:0] sum_low;
wire carry;

partition_0 p0 (
    .a(a),
    .b(b),
    .sum_low(sum_low),
    .carry(carry)
);

assign sum = {carry, sum_low};

endmodule
"""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'partition_0.v', 'w') as f:
        f.write(partition_0_content)
    
    with open(output_dir / 'top.v', 'w') as f:
        f.write(top_content)


def create_non_equivalent_hierarchical_netlists(output_dir: Path):
    """创建不等价的层级化网表（错误案例，用于测试）"""
    
    # 子模块1: 错误的加法（减法）
    partition_0_content = """
module partition_0 (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [3:0] sum_low,
    output wire carry
);

// 错误：这里应该是加法，但实现成了减法
assign {carry, sum_low} = a - b;

endmodule
"""
    
    # 顶层: 使用子模块
    top_content = """
module adder (
    input wire [3:0] a,
    input wire [3:0] b,
    output wire [4:0] sum
);

wire [3:0] sum_low;
wire carry;

partition_0 p0 (
    .a(a),
    .b(b),
    .sum_low(sum_low),
    .carry(carry)
);

assign sum = {carry, sum_low};

endmodule
"""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'partition_0.v', 'w') as f:
        f.write(partition_0_content)
    
    with open(output_dir / 'top.v', 'w') as f:
        f.write(top_content)


def test_yosys_available():
    """测试Yosys是否真的可用"""
    print("\n" + "="*80)
    print("TEST: Yosys真实可用性测试")
    print("="*80)
    
    verifier = FormalVerifier()
    
    # 如果Yosys不可用，这个测试会失败
    print("✓ Yosys已安装并可用")


def test_equivalent_verification():
    """测试等价网表的验证（应该通过）"""
    print("\n" + "="*80)
    print("TEST: 等价网表验证（应该成功）")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        output_dir = tmpdir / "verification"
        
        create_simple_flat_netlist(flat_netlist)
        create_equivalent_hierarchical_netlists(hierarchical_dir)
        
        verifier = FormalVerifier()
        
        result = verifier.verify_equivalence(
            flat_netlist=flat_netlist,
            top_netlist=hierarchical_dir / 'top.v',
            partition_netlists=[hierarchical_dir / 'partition_0.v'],
            output_dir=output_dir,
            top_module_name='adder',
            use_equiv_simple=True
        )
        
        print(f"\n结果：")
        print(f"  Success: {result['success']}")
        print(f"  Equivalent: {result['equivalent']}")
        print(f"  Runtime: {result['runtime']:.2f}s")
        
        if result['log_path']:
            print(f"  Log: {result['log_path']}")
        
        if result['error_message']:
            print(f"  Error: {result['error_message']}")
        
        # 断言：应该验证成功且等价
        if not result['success']:
            print(f"\n⚠️ 警告：Yosys执行失败")
            print(f"这可能是因为Yosys版本或环境问题")
            print(f"请检查Yosys安装：yosys -V")
            return False
        
        if not result['equivalent']:
            print(f"\n✗ 失败：等价网表未通过验证！")
            if result['log_path'] and result['log_path'].exists():
                print(f"\nYosys日志内容：")
                with open(result['log_path'], 'r') as f:
                    print(f.read())
            return False
        
        print(f"\n✓ 成功：等价性验证通过！")
        return True


def test_non_equivalent_verification():
    """测试不等价网表的验证（应该失败）"""
    print("\n" + "="*80)
    print("TEST: 不等价网表验证（应该检测出不等价）")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        output_dir = tmpdir / "verification"
        
        create_simple_flat_netlist(flat_netlist)
        create_non_equivalent_hierarchical_netlists(hierarchical_dir)
        
        verifier = FormalVerifier()
        
        result = verifier.verify_equivalence(
            flat_netlist=flat_netlist,
            top_netlist=hierarchical_dir / 'top.v',
            partition_netlists=[hierarchical_dir / 'partition_0.v'],
            output_dir=output_dir,
            top_module_name='adder',
            use_equiv_simple=True
        )
        
        print(f"\n结果：")
        print(f"  Success: {result['success']}")
        print(f"  Equivalent: {result['equivalent']}")
        print(f"  Runtime: {result['runtime']:.2f}s")
        
        if result['error_message']:
            print(f"  Error: {result['error_message']}")
        
        # 断言：Yosys应该成功运行，但检测出不等价
        if not result['success']:
            print(f"\n⚠️ 警告：Yosys执行失败")
            return False
        
        if result['equivalent']:
            print(f"\n✗ 失败：未能检测出不等价！")
            return False
        
        print(f"\n✓ 成功：正确检测出不等价！")
        return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*80)
    print("FORMAL VERIFICATION - 完整集成测试（真实Yosys）")
    print("="*80)
    
    results = []
    
    try:
        test_yosys_available()
        results.append(("Yosys可用性", True))
    except Exception as e:
        print(f"\n✗ Yosys不可用: {e}")
        print(f"\n请确保Yosys已安装：brew install yosys")
        print(f"或访问：https://github.com/YosysHQ/yosys")
        results.append(("Yosys可用性", False))
        return False
    
    try:
        success1 = test_equivalent_verification()
        results.append(("等价网表验证", success1))
    except Exception as e:
        print(f"\n✗ 等价网表测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("等价网表验证", False))
    
    try:
        success2 = test_non_equivalent_verification()
        results.append(("不等价网表验证", success2))
    except Exception as e:
        print(f"\n✗ 不等价网表测试异常: {e}")
        import traceback
        traceback.print_exc()
        results.append(("不等价网表验证", False))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{status}: {test_name}")
    
    all_passed = all(success for _, success in results)
    
    print("\n" + "="*80)
    if all_passed:
        print("所有测试通过 ✓")
        print("Yosys集成完全正常！")
    else:
        print("部分测试失败 ✗")
        print("请检查Yosys安装和配置")
    print("="*80)
    
    return all_passed


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

