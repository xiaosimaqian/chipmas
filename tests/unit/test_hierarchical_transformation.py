"""
层级化改造模块测试
"""

from pathlib import Path
import json
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.hierarchical_transformation import (
    HierarchicalTransformation,
    perform_hierarchical_transformation
)


def test_hierarchical_transformation_init():
    """测试初始化"""
    design_name = "test_design"
    design_dir = Path("/tmp/test")
    
    transformer = HierarchicalTransformation(design_name, design_dir)
    
    assert transformer.design_name == design_name
    assert transformer.design_dir == design_dir
    assert transformer.flat_netlist is None
    assert transformer.partition_scheme is None


def test_parse_connections():
    """测试连接解析"""
    design_name = "test"
    design_dir = Path("/tmp/test")
    
    transformer = HierarchicalTransformation(design_name, design_dir)
    
    # 测试连接字符串解析
    conn_str = ".clk(net_clk), .rst(net_rst), .data_in(net_d_in)"
    connections = transformer._parse_connections(conn_str)
    
    assert connections == {
        'clk': 'net_clk',
        'rst': 'net_rst',
        'data_in': 'net_d_in'
    }


def test_simple_partition_scheme():
    """测试简单分区方案"""
    # 创建一个简单的测试设计
    test_dir = Path("/tmp/hierarchical_test")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 简单的Verilog网表
    verilog_content = """
module test_design (
  input clk,
  input rst,
  output [7:0] out
);

  wire net1, net2, net3;
  
  inv01 u1 (.A(clk), .Z(net1));
  and02 u2 (.A(net1), .B(rst), .Z(net2));
  or02 u3 (.A(net2), .B(net1), .Z(net3));
  buf01 u4 (.A(net3), .Z(out[0]));

endmodule
"""
    
    design_file = test_dir / 'design.v'
    with open(design_file, 'w') as f:
        f.write(verilog_content)
    
    # 分区方案：u1,u2 -> partition 0; u3,u4 -> partition 1
    partition_scheme = {
        'u1': 0,
        'u2': 0,
        'u3': 1,
        'u4': 1
    }
    
    # 执行层级化改造
    output_dir = test_dir / 'hierarchical_output'
    
    try:
        result = perform_hierarchical_transformation(
            design_name='test_design',
            design_dir=test_dir,
            partition_scheme=partition_scheme,
            output_dir=output_dir
        )
        
        # 验证结果
        assert 'top_netlist' in result
        assert 'partition_netlists' in result
        assert 'boundary_connections' in result
        assert 'statistics' in result
        
        # 验证统计信息
        stats = result['statistics']
        assert stats['num_partitions'] == 2
        assert stats['total_modules'] == 4
        assert stats['partition_sizes'] == {0: 2, 1: 2}
        
        # 验证文件生成
        assert Path(result['top_netlist']).exists()
        assert Path(result['partition_netlists'][0]).exists()
        assert Path(result['partition_netlists'][1]).exists()
        
        print("\n✅ 测试通过！")
        print(f"结果: {json.dumps(result['statistics'], indent=2)}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("="*80)
    print("测试层级化改造模块")
    print("="*80)
    
    # 运行测试
    test_hierarchical_transformation_init()
    print("✓ 测试1: 初始化")
    
    test_parse_connections()
    print("✓ 测试2: 连接解析")
    
    test_simple_partition_scheme()
    print("✓ 测试3: 简单分区")
    
    print("\n" + "="*80)
    print("所有测试完成!")
    print("="*80)

