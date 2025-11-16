"""
VerilogPartitioner单元测试
"""

import sys
from pathlib import Path
import json
import tempfile
import shutil

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.verilog_partitioner import VerilogPartitioner, perform_verilog_partitioning


def create_test_design():
    """创建测试用的门级网表"""
    verilog_content = """module simple_design (
    input clk,
    input reset,
    input [3:0] data_in,
    output [3:0] data_out
);
    wire w1, w2, w3, w4;
    wire [3:0] internal_bus;
    
    // Partition 0的instances
    AND2 u_and1 (
        .A(data_in[0]),
        .B(data_in[1]),
        .Y(w1)
    );
    
    OR2 u_or1 (
        .A(w1),
        .B(data_in[2]),
        .Y(w2)
    );
    
    // Partition 1的instances
    XOR2 u_xor1 (
        .A(w2),
        .B(data_in[3]),
        .Y(w3)
    );
    
    BUF u_buf1 (
        .A(w3),
        .Y(data_out[0])
    );
    
    // Partition 0的另一个instance
    INV u_inv1 (
        .A(clk),
        .Y(w4)
    );
    
    // Partition 1的另一个instance
    DFF u_dff1 (
        .CLK(w4),
        .D(reset),
        .Q(data_out[1])
    );
    
endmodule
"""
    return verilog_content


def create_test_partition_scheme():
    """创建测试分区方案"""
    # 分区方案：
    # Partition 0: u_and1, u_or1, u_inv1
    # Partition 1: u_xor1, u_buf1, u_dff1
    
    # 创建.part.2文件（6行，每行一个partition ID）
    part_content = """0
0
1
1
0
1
"""
    
    # 创建mapping.json
    mapping = {
        "vertex_to_id": {
            "u_and1": 1,
            "u_or1": 2,
            "u_xor1": 3,
            "u_buf1": 4,
            "u_inv1": 5,
            "u_dff1": 6
        }
    }
    
    return part_content, mapping


def test_verilog_partitioner_basic():
    """测试基本功能"""
    print("=" * 60)
    print("测试: VerilogPartitioner基本功能")
    print("=" * 60)
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 1. 创建测试文件
        design_v = tmpdir / "design.v"
        part_file = tmpdir / "design.part.2"
        mapping_file = tmpdir / "design.mapping.json"
        output_dir = tmpdir / "output"
        
        # 写入测试数据
        with open(design_v, 'w') as f:
            f.write(create_test_design())
        
        part_content, mapping = create_test_partition_scheme()
        with open(part_file, 'w') as f:
            f.write(part_content)
        
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f)
        
        # 2. 执行分区
        print("\n执行分区...")
        result = perform_verilog_partitioning(
            design_v,
            part_file,
            mapping_file,
            output_dir
        )
        
        # 3. 验证结果
        print("\n验证结果...")
        
        # 3.1 检查文件生成
        assert output_dir.exists(), "输出目录未创建"
        assert result['top_file'].exists(), "top.v未生成"
        assert result['boundary_file'].exists(), "boundary_nets.json未生成"
        
        for pid, pfile in result['partition_files'].items():
            assert pfile.exists(), f"partition_{pid}.v未生成"
            print(f"  ✓ partition_{pid}.v 生成")
        
        print(f"  ✓ top.v 生成")
        print(f"  ✓ boundary_nets.json 生成")
        
        # 3.2 检查统计信息
        stats = result['stats']
        print(f"\n统计信息:")
        print(f"  分区数: {stats['num_partitions']}")
        print(f"  总instances: {stats['num_instances']}")
        print(f"  总nets: {stats['num_nets']}")
        print(f"  Boundary nets: {stats['num_boundary_nets']}")
        print(f"  Internal nets: {stats['num_internal_nets']}")
        
        assert stats['num_partitions'] == 2, "分区数量错误"
        assert stats['num_instances'] == 6, "Instance数量错误"
        
        # 3.3 检查boundary nets
        boundary_nets = result['boundary_nets']
        print(f"\nBoundary nets:")
        for net_name, info in boundary_nets.items():
            print(f"  {net_name}: partitions={info['partitions']}")
        
        # w2应该是boundary net（连接partition 0和1）
        assert 'w2' in boundary_nets, "w2应该是boundary net"
        assert set(boundary_nets['w2']['partitions']) == {0, 1}, "w2应该连接partition 0和1"
        
        # 3.4 检查生成的文件内容
        print("\n检查partition_0.v内容:")
        with open(result['partition_files'][0], 'r') as f:
            p0_content = f.read()
            print(p0_content[:300] + "...")
            assert "module partition_0" in p0_content
            assert "u_and1" in p0_content
            assert "u_or1" in p0_content
            assert "u_inv1" in p0_content
        
        print("\n检查top.v内容:")
        with open(result['top_file'], 'r') as f:
            top_content = f.read()
            print(top_content[:300] + "...")
            assert "module simple_design" in top_content
            assert "partition_0 u_partition_0" in top_content
            assert "partition_1 u_partition_1" in top_content
        
        print("\n" + "=" * 60)
        print("✓ VerilogPartitioner基本功能测试通过！")
        print("=" * 60)


def test_verilog_partitioner_parsing():
    """测试Verilog解析功能"""
    print("\n" + "=" * 60)
    print("测试: Verilog解析功能")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # 创建测试文件
        design_v = tmpdir / "design.v"
        part_file = tmpdir / "design.part.2"
        mapping_file = tmpdir / "design.mapping.json"
        
        with open(design_v, 'w') as f:
            f.write(create_test_design())
        
        part_content, mapping = create_test_partition_scheme()
        with open(part_file, 'w') as f:
            f.write(part_content)
        
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f)
        
        # 创建partitioner并解析
        partitioner = VerilogPartitioner(design_v, part_file, mapping_file)
        
        # 测试解析
        partitioner._parse_design_netlist()
        
        print(f"\n解析结果:")
        print(f"  顶层模块: {partitioner.top_module_name}")
        print(f"  顶层端口数: {len(partitioner.top_ports)}")
        print(f"  Instance数: {len(partitioner.instances)}")
        print(f"  Net数: {len(partitioner.nets)}")
        
        # 验证解析结果
        assert partitioner.top_module_name == "simple_design"
        # 端口可能解析数量不同（data_in和data_out可能算作多个）
        assert len(partitioner.top_ports) >= 3  # 至少clk, reset, data_in/data_out
        assert len(partitioner.instances) == 6
        assert "u_and1" in partitioner.instances
        assert "u_xor1" in partitioner.instances
        
        # 验证net连接
        assert "w1" in partitioner.nets
        assert "w2" in partitioner.nets
        
        print("\n✓ Verilog解析功能测试通过！")


def test_boundary_detection():
    """测试boundary net识别"""
    print("\n" + "=" * 60)
    print("测试: Boundary Net识别")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        design_v = tmpdir / "design.v"
        part_file = tmpdir / "design.part.2"
        mapping_file = tmpdir / "design.mapping.json"
        
        with open(design_v, 'w') as f:
            f.write(create_test_design())
        
        part_content, mapping = create_test_partition_scheme()
        with open(part_file, 'w') as f:
            f.write(part_content)
        
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f)
        
        # 创建并初始化partitioner
        partitioner = VerilogPartitioner(design_v, part_file, mapping_file)
        partitioner._parse_design_netlist()
        partitioner._parse_kspecpart_result()
        partitioner._identify_boundary_nets()
        
        print(f"\nBoundary nets识别结果:")
        print(f"  Boundary nets数量: {len(partitioner.boundary_nets)}")
        print(f"  Boundary nets:")
        for net_name, info in partitioner.boundary_nets.items():
            print(f"    - {net_name}: {info['partitions']}")
        
        print(f"\n  Internal nets (Partition 0): {len(partitioner.internal_nets[0])}")
        print(f"  Internal nets (Partition 1): {len(partitioner.internal_nets[1])}")
        
        # 验证
        # w1是internal（u_and1和u_or1都在partition 0）
        assert 'w1' in partitioner.internal_nets[0], "w1应该是partition 0的internal net"
        
        # w2是boundary（u_or1在partition 0, u_xor1在partition 1）
        assert 'w2' in partitioner.boundary_nets, "w2应该是boundary net"
        
        # w4是boundary（u_inv1在partition 0, u_dff1在partition 1）
        assert 'w4' in partitioner.boundary_nets, "w4应该是boundary net"
        
        print("\n✓ Boundary Net识别测试通过！")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("VerilogPartitioner 单元测试")
    print("=" * 60)
    
    try:
        test_verilog_partitioner_parsing()
        test_boundary_detection()
        test_verilog_partitioner_basic()
        
        print("\n" + "=" * 60)
        print("✓✓✓ 所有测试通过！✓✓✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()

