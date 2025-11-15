"""
层级化改造模块

将扁平网表转换为层次化网表（顶层 + 各分区）
"""

from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
import json
import re
from collections import defaultdict


class HierarchicalTransformation:
    """层级化改造类"""
    
    def __init__(self, design_name: str, design_dir: Path):
        """
        初始化
        
        Args:
            design_name: 设计名称
            design_dir: 设计目录（包含design.v）
        """
        self.design_name = design_name
        self.design_dir = Path(design_dir)
        self.flat_netlist_path = self.design_dir / 'design.v'
        
        # 解析结果
        self.flat_netlist = None  # 扁平网表内容
        self.partition_scheme = None  # {module_name: partition_id}
        self.modules = {}  # {module_name: module_info}
        self.nets = {}  # {net_name: net_info}
        self.top_module_name = None  # 顶层模块名
        self.top_module_ports = {}  # {port_name: {'direction': 'input'/'output', 'nets': [net_names]}}
        self.boundary_connections = {}  # 边界连接信息
        self.partition_netlists = {}  # 分区网表
        self.top_netlist = None  # 顶层网表
        
    def analyze_boundary_connections(
        self,
        partition_scheme: Dict[str, int]
    ) -> Dict[str, Dict]:
        """
        分析跨分区连接
        
        Args:
            partition_scheme: {module_name: partition_id}
            
        Returns:
            boundary_connections: {
                net_name: {
                    'partitions': [p1, p2, ...],  # 涉及的分区ID
                    'pins': [(module, pin), ...],  # 该net的所有引脚
                    'is_boundary': True/False      # 是否跨分区
                }
            }
        """
        self.partition_scheme = partition_scheme
        
        # 1. 解析扁平网表
        print(f"正在解析扁平网表: {self.flat_netlist_path}")
        self._parse_flat_netlist()
        
        # 2. 遍历所有net，分析跨分区连接
        print("正在分析边界连接...")
        boundary_connections = {}
        
        for net_name, net_info in self.nets.items():
            # 获取该net涉及的所有模块
            connected_modules = set()
            for module_name, pin in net_info['pins']:
                connected_modules.add(module_name)
            
            # 获取这些模块所属的分区
            connected_partitions = set()
            for module_name in connected_modules:
                if module_name in partition_scheme:
                    connected_partitions.add(partition_scheme[module_name])
            
            # 判断是否跨分区
            is_boundary = len(connected_partitions) > 1
            
            boundary_connections[net_name] = {
                'partitions': sorted(list(connected_partitions)),
                'pins': net_info['pins'],
                'is_boundary': is_boundary,
                'driver': net_info.get('driver'),  # (module, pin)
                'loads': net_info.get('loads', [])  # [(module, pin), ...]
            }
        
        # 统计边界net数量
        num_boundary_nets = sum(1 for info in boundary_connections.values() if info['is_boundary'])
        print(f"✓ 发现 {num_boundary_nets} 个边界net（总共 {len(boundary_connections)} 个net）")
        
        self.boundary_connections = boundary_connections
        return boundary_connections
    
    def _parse_flat_netlist(self):
        """解析扁平网表（Verilog）"""
        with open(self.flat_netlist_path, 'r') as f:
            content = f.read()
        
        self.flat_netlist = content
        
        # 1. 解析顶层模块定义
        self._parse_top_module(content)
        
        # 2. 解析模块实例化
        # 匹配: module_type instance_name ( .port1(net1), .port2(net2), ... );
        instance_pattern = re.compile(
            r'(\w+)\s+(\w+)\s*\((.*?)\)\s*;',
            re.DOTALL
        )
        
        for match in instance_pattern.finditer(content):
            module_type = match.group(1)
            instance_name = match.group(2)
            connections_str = match.group(3)
            
            # 跳过顶层模块定义
            if module_type == 'module':
                continue
            
            # 解析连接
            connections = self._parse_connections(connections_str)
            
            self.modules[instance_name] = {
                'type': module_type,
                'connections': connections  # {port: net}
            }
            
            # 更新nets信息
            for port, net in connections.items():
                if net not in self.nets:
                    self.nets[net] = {
                        'pins': [],
                        'driver': None,
                        'loads': []
                    }
                self.nets[net]['pins'].append((instance_name, port))
        
        print(f"✓ 解析完成: {len(self.modules)} 个模块, {len(self.nets)} 个net")
    
    def _parse_top_module(self, content: str):
        """解析顶层模块定义，提取端口信息"""
        # 匹配顶层模块定义
        # module module_name ( port1, port2, ... );
        module_pattern = re.compile(
            r'module\s+(\w+)\s*\((.*?)\);',
            re.DOTALL
        )
        
        match = module_pattern.search(content)
        if not match:
            return
        
        self.top_module_name = match.group(1)
        ports_str = match.group(2)
        
        # 解析端口声明（input/output）
        # 支持格式: input wire [3:0] a, 或 output wire cout
        port_pattern = re.compile(
            r'(input|output)\s+wire\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)',
            re.MULTILINE
        )
        
        for port_match in port_pattern.finditer(content):
            direction = port_match.group(1)
            msb = port_match.group(2)
            lsb = port_match.group(3)
            port_name = port_match.group(4)
            
            # 解析向量端口 (如 a[3:0])
            if msb and lsb:
                msb_val, lsb_val = int(msb), int(lsb)
                # 生成每个bit的net名
                for i in range(lsb_val, msb_val + 1):
                    net_name = f"{port_name}[{i}]"
                    self.top_module_ports[net_name] = {
                        'direction': direction,
                        'port_base': port_name,
                        'bit': i
                    }
            else:
                # 标量端口
                self.top_module_ports[port_name] = {
                    'direction': direction,
                    'port_base': port_name,
                    'bit': None
                }
    
    def _parse_connections(self, connections_str: str) -> Dict[str, str]:
        """解析模块连接字符串"""
        connections = {}
        
        # 匹配 .port(net) 格式，支持向量索引
        conn_pattern = re.compile(r'\.(\w+)\s*\(\s*([\w\[\]]+)\s*\)')
        
        for match in conn_pattern.finditer(connections_str):
            port = match.group(1)
            net = match.group(2)
            connections[port] = net
        
        return connections
    
    def extract_partition_netlist(
        self,
        partition_id: int,
        output_dir: Path
    ) -> Path:
        """
        提取单个分区的网表
        
        Args:
            partition_id: 分区ID
            output_dir: 输出目录
            
        Returns:
            partition_netlist_path: 分区网表路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n提取分区 {partition_id} 的网表...")
        
        # 1. 获取该分区的所有module
        partition_modules = [
            name for name, pid in self.partition_scheme.items()
            if pid == partition_id
        ]
        
        print(f"  - 模块数: {len(partition_modules)}")
        
        # 2. 识别边界net和内部net
        boundary_nets = []
        internal_nets = []
        
        for net_name, net_info in self.boundary_connections.items():
            if partition_id in net_info['partitions']:
                if net_info['is_boundary']:
                    boundary_nets.append(net_name)
                else:
                    # 纯内部net
                    pins_in_partition = [
                        (m, p) for m, p in net_info['pins']
                        if m in partition_modules
                    ]
                    if len(pins_in_partition) > 0:
                        internal_nets.append(net_name)
        
        print(f"  - 边界net: {len(boundary_nets)}")
        print(f"  - 内部net: {len(internal_nets)}")
        
        # 3. 为边界net推断端口方向
        boundary_ports = self._infer_port_directions(
            partition_id,
            partition_modules,
            boundary_nets
        )
        
        # 4. 生成Verilog模块
        verilog_content = self._generate_partition_verilog(
            partition_id,
            partition_modules,
            boundary_ports,
            internal_nets
        )
        
        # 5. 保存到文件
        output_file = output_dir / f'partition_{partition_id}.v'
        with open(output_file, 'w') as f:
            f.write(verilog_content)
        
        print(f"✓ 分区网表已保存: {output_file}")
        
        return output_file
    
    def _infer_port_directions(
        self,
        partition_id: int,
        partition_modules: List[str],
        boundary_nets: List[str]
    ) -> List[Dict]:
        """
        推断边界端口的方向
        
        Returns:
            boundary_ports: [
                {'name': net_name, 'direction': 'input'/'output'/'inout'},
                ...
            ]
        """
        boundary_ports = []
        
        for net_name in boundary_nets:
            net_info = self.boundary_connections[net_name]
            
            # 分析driver和load的位置
            driver = net_info.get('driver')
            loads = net_info.get('loads', [])
            
            # 简单推断规则（后续可以改进）
            driver_in_partition = driver and driver[0] in partition_modules
            loads_in_partition = any(m in partition_modules for m, p in loads)
            
            if driver_in_partition and not loads_in_partition:
                direction = 'output'
            elif not driver_in_partition and loads_in_partition:
                direction = 'input'
            else:
                # 既有driver又有load，或者无法确定
                direction = 'inout'
            
            boundary_ports.append({
                'name': net_name,
                'direction': direction
            })
        
        return boundary_ports
    
    def _generate_partition_verilog(
        self,
        partition_id: int,
        partition_modules: List[str],
        boundary_ports: List[Dict],
        internal_nets: List[str]
    ) -> str:
        """生成分区Verilog代码"""
        lines = []
        
        # 模块声明
        lines.append(f"module partition_{partition_id} (")
        
        # 端口列表
        port_decls = []
        for port in boundary_ports:
            port_decls.append(f"  {port['direction']} wire {port['name']}")
        lines.append(",\n".join(port_decls))
        lines.append(");\n")
        
        # 内部信号声明
        if internal_nets:
            lines.append("  // Internal nets")
            for net in internal_nets:
                lines.append(f"  wire {net};")
            lines.append("")
        
        # 模块实例化
        lines.append("  // Module instances")
        for module_name in partition_modules:
            if module_name not in self.modules:
                continue
            
            module_info = self.modules[module_name]
            module_type = module_info['type']
            connections = module_info['connections']
            
            lines.append(f"  {module_type} {module_name} (")
            
            # 连接
            conn_strs = []
            for port, net in connections.items():
                conn_strs.append(f"    .{port}({net})")
            lines.append(",\n".join(conn_strs))
            lines.append("  );\n")
        
        lines.append("endmodule\n")
        
        return "\n".join(lines)
    
    def generate_top_netlist(
        self,
        num_partitions: int,
        output_dir: Path
    ) -> Path:
        """
        生成顶层网表
        
        Args:
            num_partitions: 分区数量
            output_dir: 输出目录
            
        Returns:
            top_netlist_path: 顶层网表路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n生成顶层网表...")
        
        # 收集所有边界net
        boundary_nets = [
            name for name, info in self.boundary_connections.items()
            if info['is_boundary']
        ]
        
        print(f"  - 边界net数: {len(boundary_nets)}")
        
        # 生成Verilog
        lines = []
        lines.append("module top (")
        lines.append("  // TODO: 添加顶层输入输出端口")
        lines.append(");\n")
        
        # 边界信号声明
        lines.append("  // Boundary nets")
        for net in boundary_nets:
            lines.append(f"  wire {net};")
        lines.append("")
        
        # 实例化各分区
        lines.append("  // Partition instances")
        for pid in range(num_partitions):
            lines.append(f"  partition_{pid} part{pid}_inst (")
            
            # 连接边界net
            # TODO: 根据实际boundary_ports连接
            lines.append("    // TODO: 连接边界端口")
            lines.append("  );\n")
        
        lines.append("endmodule\n")
        
        verilog_content = "\n".join(lines)
        
        # 保存
        output_file = output_dir / 'top.v'
        with open(output_file, 'w') as f:
            f.write(verilog_content)
        
        print(f"✓ 顶层网表已保存: {output_file}")
        
        return output_file


def perform_hierarchical_transformation(
    design_name: str,
    design_dir: Path,
    partition_scheme: Dict[str, int],
    output_dir: Path
) -> Dict:
    """
    执行完整的层级化改造
    
    Args:
        design_name: 设计名称
        design_dir: 设计目录
        partition_scheme: 分区方案 {module: partition_id}
        output_dir: 输出目录
        
    Returns:
        result: {
            'top_netlist': Path,
            'partition_netlists': {0: Path, 1: Path, ...},
            'boundary_connections': Dict,
            'statistics': {
                'num_partitions': int,
                'num_boundary_nets': int,
                'partition_sizes': {0: int, 1: int, ...}
            }
        }
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"开始层级化改造: {design_name}")
    print(f"{'='*80}\n")
    
    transformer = HierarchicalTransformation(design_name, design_dir)
    
    # 1. 分析边界连接
    boundary_conns = transformer.analyze_boundary_connections(partition_scheme)
    
    # 2. 提取各分区网表
    partition_netlists = {}
    num_partitions = max(partition_scheme.values()) + 1
    
    for pid in range(num_partitions):
        netlist_path = transformer.extract_partition_netlist(pid, output_dir)
        partition_netlists[pid] = netlist_path
    
    # 3. 生成顶层网表
    top_netlist = transformer.generate_top_netlist(num_partitions, output_dir)
    
    # 4. 统计信息
    partition_sizes = defaultdict(int)
    for module, pid in partition_scheme.items():
        partition_sizes[pid] += 1
    
    num_boundary_nets = sum(1 for info in boundary_conns.values() if info['is_boundary'])
    
    statistics = {
        'num_partitions': num_partitions,
        'num_boundary_nets': num_boundary_nets,
        'total_modules': len(partition_scheme),
        'total_nets': len(boundary_conns),
        'partition_sizes': dict(partition_sizes)
    }
    
    # 5. 保存结果
    result = {
        'top_netlist': str(top_netlist),
        'partition_netlists': {k: str(v) for k, v in partition_netlists.items()},
        'boundary_connections': boundary_conns,
        'statistics': statistics
    }
    
    result_file = output_dir / 'hierarchical_info.json'
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n{'='*80}")
    print(f"层级化改造完成!")
    print(f"{'='*80}")
    print(f"统计信息:")
    print(f"  - 分区数: {statistics['num_partitions']}")
    print(f"  - 边界net数: {statistics['num_boundary_nets']}")
    print(f"  - 总模块数: {statistics['total_modules']}")
    print(f"  - 总net数: {statistics['total_nets']}")
    print(f"  - 分区大小: {statistics['partition_sizes']}")
    print(f"  - 结果保存至: {output_dir}")
    print()
    
    return result

