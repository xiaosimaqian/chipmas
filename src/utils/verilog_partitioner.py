"""
Verilog Partitioner - 基于K-SpecPart结果生成分区网表

功能：
1. 解析flatten门级网表（design.v）
2. 解析K-SpecPart分区结果（.part.4 + .mapping.json）
3. 识别boundary nets（跨partition的nets）
4. 生成partition子网表（partition_0.v ~ partition_K-1.v）
5. 生成顶层网表（top.v，实例化所有partition模块）
6. 支持Formal验证集成

作者：ChipMASRAG Team
日期：2025-11-15
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Port:
    """端口信息"""
    name: str
    direction: str  # 'input' or 'output' or 'inout'
    width: int = 1  # 位宽
    is_vector: bool = False  # 是否是向量
    
    def to_verilog(self) -> str:
        """转换为Verilog声明"""
        if self.is_vector and self.width > 1:
            return f"{self.direction} [{self.width-1}:0] {self.name}"
        else:
            return f"{self.direction} {self.name}"


@dataclass
class Net:
    """网络信息"""
    name: str
    width: int = 1
    is_vector: bool = False
    connected_instances: List[str] = None  # 连接的instance名称列表
    
    def __post_init__(self):
        if self.connected_instances is None:
            self.connected_instances = []


@dataclass
class Instance:
    """实例信息"""
    name: str
    module_type: str
    connections: Dict[str, str]  # {pin_name: net_name}


class VerilogPartitioner:
    """
    Verilog分区器
    
    基于K-SpecPart的逻辑分区决策，生成实际的分区网表
    """
    
    def __init__(self, design_v: Path, part_file: Path, mapping_file: Path):
        """
        初始化
        
        Args:
            design_v: 原始flatten门级网表路径
            part_file: K-SpecPart输出的.part.K文件
            mapping_file: component名称到vertex ID的映射文件
        """
        self.design_v = Path(design_v)
        self.part_file = Path(part_file)
        self.mapping_file = Path(mapping_file)
        
        # 解析结果
        self.top_module_name = None
        self.top_ports = []  # List[Port]
        self.instances = {}  # {instance_name: Instance}
        self.nets = {}  # {net_name: Net}
        self.partition_scheme = {}  # {instance_name: partition_id}
        self.num_partitions = 0
        
        # 分区分析结果
        self.internal_nets = {}  # {partition_id: [net_names]}
        self.boundary_nets = {}  # {net_name: {'partitions': [ids], 'type': 'inter'}}
        
        logger.info(f"初始化VerilogPartitioner")
        logger.info(f"  设计网表: {self.design_v}")
        logger.info(f"  分区文件: {self.part_file}")
        logger.info(f"  映射文件: {self.mapping_file}")
    
    def partition(self, output_dir: Path) -> Dict:
        """
        执行分区处理
        
        Args:
            output_dir: 输出目录
            
        Returns:
            Dict包含:
            - partition_files: {0: Path, 1: Path, ...}
            - top_file: Path
            - boundary_nets: Dict
            - stats: Dict
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("=" * 60)
        logger.info("开始Verilog分区处理")
        logger.info("=" * 60)
        
        # Step 1: 解析原始netlist
        logger.info("\nStep 1: 解析原始门级网表...")
        self._parse_design_netlist()
        logger.info(f"  ✅ 解析完成：{len(self.instances)} instances, {len(self.nets)} nets")
        
        # Step 2: 解析K-SpecPart结果
        logger.info("\nStep 2: 解析K-SpecPart分区结果...")
        self._parse_kspecpart_result()
        logger.info(f"  ✅ 分区方案加载完成：{self.num_partitions} 个分区")
        for pid in range(self.num_partitions):
            count = sum(1 for p in self.partition_scheme.values() if p == pid)
            pct = count / len(self.partition_scheme) * 100
            logger.info(f"     Partition {pid}: {count} instances ({pct:.1f}%)")
        
        # Step 3: 识别boundary nets
        logger.info("\nStep 3: 识别boundary nets...")
        self._identify_boundary_nets()
        total_internal = sum(len(nets) for nets in self.internal_nets.values())
        logger.info(f"  ✅ Boundary nets: {len(self.boundary_nets)}")
        logger.info(f"  ✅ Internal nets: {total_internal}")
        
        # Step 4: 生成partition子网表
        logger.info("\nStep 4: 生成partition子网表...")
        partition_files = {}
        for pid in range(self.num_partitions):
            partition_file = output_dir / f"partition_{pid}.v"
            self._generate_partition_netlist(pid, partition_file)
            partition_files[pid] = partition_file
            logger.info(f"  ✅ partition_{pid}.v 生成完成")
        
        # Step 5: 生成顶层网表
        logger.info("\nStep 5: 生成顶层网表...")
        top_file = output_dir / "top.v"
        self._generate_top_netlist(top_file)
        logger.info(f"  ✅ top.v 生成完成")
        
        # Step 6: 保存boundary nets信息
        logger.info("\nStep 6: 保存boundary nets信息...")
        boundary_file = output_dir / "boundary_nets.json"
        self._save_boundary_nets(boundary_file)
        logger.info(f"  ✅ boundary_nets.json 保存完成")
        
        # 统计信息
        stats = {
            'num_partitions': self.num_partitions,
            'num_instances': len(self.instances),
            'num_nets': len(self.nets),
            'num_boundary_nets': len(self.boundary_nets),
            'num_internal_nets': total_internal,
            'partition_sizes': {
                pid: sum(1 for p in self.partition_scheme.values() if p == pid)
                for pid in range(self.num_partitions)
            }
        }
        
        logger.info("\n" + "=" * 60)
        logger.info("Verilog分区处理完成！")
        logger.info("=" * 60)
        logger.info(f"统计信息：")
        logger.info(f"  总instances: {stats['num_instances']}")
        logger.info(f"  总nets: {stats['num_nets']}")
        logger.info(f"  Boundary nets: {stats['num_boundary_nets']}")
        logger.info(f"  Internal nets: {stats['num_internal_nets']}")
        logger.info(f"  Cutsize占比: {stats['num_boundary_nets']/stats['num_nets']*100:.2f}%")
        
        return {
            'partition_files': partition_files,
            'top_file': top_file,
            'boundary_nets': self.boundary_nets,
            'boundary_file': boundary_file,
            'stats': stats
        }
    
    def _parse_design_netlist(self):
        """解析原始门级网表"""
        with open(self.design_v, 'r') as f:
            content = f.read()
        
        # 1. 解析module定义
        module_pattern = re.compile(
            r'module\s+(\w+)\s*\((.*?)\);',
            re.DOTALL
        )
        module_match = module_pattern.search(content)
        if not module_match:
            raise ValueError("无法找到module定义")
        
        self.top_module_name = module_match.group(1)
        logger.info(f"  顶层模块: {self.top_module_name}")
        
        # 2. 解析端口声明
        port_pattern = re.compile(
            r'(input|output|inout)\s+(?:wire\s+)?(?:\[(\d+):(\d+)\]\s+)?(\w+)\s*[;,]',
            re.MULTILINE
        )
        for match in port_pattern.finditer(content):
            direction = match.group(1)
            msb = match.group(2)
            lsb = match.group(3)
            port_name = match.group(4)
            
            if msb and lsb:
                width = int(msb) - int(lsb) + 1
                is_vector = True
            else:
                width = 1
                is_vector = False
            
            port = Port(port_name, direction, width, is_vector)
            self.top_ports.append(port)
            
            # 将端口添加到nets中（特别是output和inout端口，它们可能被instance连接）
            # 这样在解析instance连接时，可以正确记录连接关系
            if direction in ['output', 'inout']:
                if port_name not in self.nets:
                    self.nets[port_name] = Net(port_name, width, is_vector)
        
        logger.info(f"  顶层端口: {len(self.top_ports)}")
        
        # 3. 解析wire声明
        wire_pattern = re.compile(
            r'wire\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)\s*;',
            re.MULTILINE
        )
        for match in wire_pattern.finditer(content):
            msb = match.group(1)
            lsb = match.group(2)
            net_name = match.group(3)
            
            if msb and lsb:
                width = int(msb) - int(lsb) + 1
                is_vector = True
            else:
                width = 1
                is_vector = False
            
            self.nets[net_name] = Net(net_name, width, is_vector)
        
        # 4. 解析instance实例化
        # 匹配模式：module_type instance_name ( .pin(net), .pin(net), ... );
        instance_pattern = re.compile(
            r'(\w+)\s+(\w+)\s*\((.*?)\)\s*;',
            re.DOTALL
        )
        
        # 从module定义之后开始解析
        module_end = module_match.end()
        instances_section = content[module_end:]
        
        for match in instance_pattern.finditer(instances_section):
            module_type = match.group(1)
            instance_name = match.group(2)
            connections_str = match.group(3)
            
            # 跳过module, endmodule等关键字
            if module_type in ['module', 'endmodule', 'input', 'output', 'inout', 'wire']:
                continue
            
            # 解析连接 .pin(net)
            connections = {}
            conn_pattern = re.compile(r'\.(\w+)\s*\(\s*(\w+(?:\[\d+\])?)\s*\)')
            for conn_match in conn_pattern.finditer(connections_str):
                pin_name = conn_match.group(1)
                net_name = conn_match.group(2)
                connections[pin_name] = net_name
                
                # 记录net的连接关系
                # 处理向量索引，如 net[0] → net
                base_net_name = net_name.split('[')[0]
                if base_net_name not in self.nets:
                    # 可能是端口或未声明的wire
                    self.nets[base_net_name] = Net(base_net_name)
                
                if instance_name not in self.nets[base_net_name].connected_instances:
                    self.nets[base_net_name].connected_instances.append(instance_name)
            
            if connections:  # 只添加有连接的instance
                self.instances[instance_name] = Instance(
                    instance_name, module_type, connections
                )
        
        logger.info(f"  解析instances: {len(self.instances)}")
        logger.info(f"  解析nets: {len(self.nets)}")
    
    def _parse_kspecpart_result(self):
        """解析K-SpecPart分区结果"""
        # 1. 读取映射文件
        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)
        
        # mapping格式: {"vertex_to_id": {"comp_name": vertex_id, ...}}
        vertex_to_id = mapping['vertex_to_id']
        id_to_vertex = {v: k for k, v in vertex_to_id.items()}
        
        # 2. 读取分区文件
        partition_assignment = {}
        with open(self.part_file, 'r') as f:
            for vertex_id, line in enumerate(f, start=1):
                part_id = int(line.strip())
                if vertex_id in id_to_vertex:
                    comp_name = id_to_vertex[vertex_id]
                    partition_assignment[comp_name] = part_id
                    
                    # 更新分区数量
                    if part_id + 1 > self.num_partitions:
                        self.num_partitions = part_id + 1
        
        # 3. 将partition_assignment应用到self.instances
        for inst_name in self.instances.keys():
            if inst_name in partition_assignment:
                self.partition_scheme[inst_name] = partition_assignment[inst_name]
            else:
                # 未在K-SpecPart结果中的instance，默认分配到partition 0
                logger.warning(f"  Instance {inst_name} 不在K-SpecPart结果中，默认分配到partition 0")
                self.partition_scheme[inst_name] = 0
    
    def _identify_boundary_nets(self):
        """识别boundary nets和internal nets"""
        # 初始化
        for pid in range(self.num_partitions):
            self.internal_nets[pid] = []
        
        # 获取顶层输出端口名称集合
        top_output_ports = {port.name for port in self.top_ports if port.direction == 'output'}
        
        # 分析每个net
        for net_name, net in self.nets.items():
            # 找出该net连接的所有partitions
            connected_partitions = set()
            for inst_name in net.connected_instances:
                if inst_name in self.partition_scheme:
                    connected_partitions.add(self.partition_scheme[inst_name])
            
            # 特殊处理：顶层输出端口
            is_top_output = net_name in top_output_ports
            
            if len(connected_partitions) == 0:
                # 如果这是顶层输出端口，且连接到某个partition的instance，应该被识别为boundary net
                if is_top_output:
                    # 检查是否有instance连接到这个输出端口
                    # 在解析时，如果instance的输出直接连接到顶层输出端口，这个连接应该已经被记录
                    # 但如果这里没有connected_partitions，可能是解析问题
                    # 为了安全，我们跳过它（但应该修复解析逻辑）
                    logger.warning(f"  顶层输出端口 {net_name} 没有连接到任何partition的instance，可能存在问题")
                continue
            elif len(connected_partitions) == 1:
                # Internal net，但如果它是顶层输出端口，应该是boundary net
                if is_top_output:
                    # 顶层输出端口即使只连接到一个partition，也应该是boundary net
                    # 因为它需要从partition传递到顶层
                    pid = connected_partitions.pop()
                    self.boundary_nets[net_name] = {
                        'partitions': [pid],
                        'type': 'top_output',
                        'connected_instances': net.connected_instances
                    }
                else:
                    # 普通internal net
                    pid = connected_partitions.pop()
                    self.internal_nets[pid].append(net_name)
            else:
                # Boundary net（跨多个partitions或顶层输出）
                self.boundary_nets[net_name] = {
                    'partitions': sorted(list(connected_partitions)),
                    'type': 'top_output' if is_top_output else 'inter_partition',
                    'connected_instances': net.connected_instances
                }
    
    def _generate_partition_netlist(self, partition_id: int, output_file: Path):
        """生成partition子网表"""
        lines = []
        
        # 1. Module声明
        module_name = f"partition_{partition_id}"
        lines.append(f"module {module_name} (")
        
        # 2. 端口列表
        ports = []
        
        # 2.1 顶层IO端口（如果该partition连接到顶层IO，且不是boundary net）
        # 注意：如果顶层输出端口是boundary net，它会在2.2中作为boundary net端口添加
        top_output_ports = {port.name for port in self.top_ports if port.direction == 'output'}
        for port in self.top_ports:
            # 检查该端口是否连接到这个partition的instance
            port_net_name = port.name
            # 如果这是顶层输出端口且是boundary net，跳过（会在2.2中处理）
            if port_net_name in top_output_ports and port_net_name in self.boundary_nets:
                continue
                
            if port_net_name in self.nets:
                net = self.nets[port_net_name]
                has_connection = any(
                    inst in self.partition_scheme and 
                    self.partition_scheme[inst] == partition_id
                    for inst in net.connected_instances
                )
                if has_connection:
                    ports.append(f"    {port.to_verilog()}")
        
        # 2.2 Boundary nets作为端口
        for net_name, bnet_info in self.boundary_nets.items():
            if partition_id in bnet_info['partitions']:
                net = self.nets[net_name]
                # 判断方向：
                # - 如果是顶层输出端口，应该是output
                # - 否则，根据是否有该partition的instance作为driver判断
                is_top_output = net_name in top_output_ports
                if is_top_output:
                    direction = "output"
                    # 对于顶层输出端口，直接使用端口名，不使用bnet_前缀
                    port_name = net_name
                else:
                    direction = "inout"  # 简化处理：默认为inout（双向）
                    port_name = f"bnet_{net_name}"
                
                if net.is_vector:
                    ports.append(f"    {direction} [{net.width-1}:0] {port_name}")
                else:
                    ports.append(f"    {direction} {port_name}")
        
        if ports:
            lines.append(",\n".join(ports))
        lines.append(");\n")
        
        # 3. Internal wires声明
        for net_name in self.internal_nets[partition_id]:
            net = self.nets[net_name]
            if net.is_vector:
                lines.append(f"    wire [{net.width-1}:0] {net_name};")
            else:
                lines.append(f"    wire {net_name};")
        
        if self.internal_nets[partition_id]:
            lines.append("")
        
        # 4. Instance实例化
        partition_instances = [
            inst_name for inst_name, pid in self.partition_scheme.items()
            if pid == partition_id
        ]
        
        for inst_name in partition_instances:
            inst = self.instances[inst_name]
            lines.append(f"    {inst.module_type} {inst_name} (")
            
            connections = []
            top_output_ports = {port.name for port in self.top_ports if port.direction == 'output'}
            for pin_name, net_name in inst.connections.items():
                # 检查是否是boundary net
                base_net = net_name.split('[')[0]
                if base_net in self.boundary_nets:
                    # 如果是顶层输出端口，直接使用端口名（不使用bnet_前缀）
                    if base_net in top_output_ports:
                        signal = base_net
                    else:
                        signal = f"bnet_{base_net}"
                    # 保留向量索引
                    if '[' in net_name:
                        idx = net_name[net_name.index('['):]
                        signal += idx
                else:
                    signal = net_name
                
                connections.append(f"        .{pin_name}({signal})")
            
            lines.append(",\n".join(connections))
            lines.append("    );\n")
        
        lines.append("endmodule\n")
        
        # 写入文件
        with open(output_file, 'w') as f:
            f.write("\n".join(lines))
    
    def _generate_top_netlist(self, output_file: Path):
        """生成顶层网表"""
        lines = []
        
        # 1. Module声明
        lines.append(f"module {self.top_module_name} (")
        
        # 2. 顶层端口（保持原样）
        ports = [f"    {port.to_verilog()}" for port in self.top_ports]
        lines.append(",\n".join(ports))
        lines.append(");\n")
        
        # 3. Boundary nets的wire声明（不包括顶层输出端口）
        top_output_ports = {port.name for port in self.top_ports if port.direction == 'output'}
        for net_name, bnet_info in self.boundary_nets.items():
            # 顶层输出端口不需要wire声明，直接连接到顶层输出端口
            if net_name in top_output_ports:
                continue
            net = self.nets[net_name]
            if net.is_vector:
                lines.append(f"    wire [{net.width-1}:0] bnet_{net_name};")
            else:
                lines.append(f"    wire bnet_{net_name};")
        
        if self.boundary_nets:
            lines.append("")
        
        # 4. 实例化各partition module
        for pid in range(self.num_partitions):
            module_name = f"partition_{pid}"
            instance_name = f"u_{module_name}"
            
            lines.append(f"    {module_name} {instance_name} (")
            
            # 收集该partition的端口连接
            connections = []
            
            # 4.1 顶层输入端口连接
            for port in self.top_ports:
                if port.direction != 'input':
                    continue
                port_net_name = port.name
                if port_net_name in self.nets:
                    net = self.nets[port_net_name]
                    has_connection = any(
                        inst in self.partition_scheme and 
                        self.partition_scheme[inst] == pid
                        for inst in net.connected_instances
                    )
                    if has_connection:
                        connections.append(f"        .{port.name}({port.name})")
            
            # 4.2 Boundary nets连接（包括顶层输出端口）
            for net_name in self.boundary_nets.keys():
                if pid in self.boundary_nets[net_name]['partitions']:
                    # 如果是顶层输出端口，直接连接到顶层输出端口
                    if net_name in top_output_ports:
                        connections.append(f"        .{net_name}({net_name})")
                    else:
                        port_name = f"bnet_{net_name}"
                        connections.append(f"        .{port_name}({port_name})")
            
            if connections:
                lines.append(",\n".join(connections))
            lines.append("    );\n")
        
        lines.append("endmodule\n")
        
        # 写入文件
        with open(output_file, 'w') as f:
            f.write("\n".join(lines))
    
    def _save_boundary_nets(self, output_file: Path):
        """保存boundary nets信息到JSON"""
        boundary_data = {
            'num_boundary_nets': len(self.boundary_nets),
            'boundary_nets': self.boundary_nets,
            'num_partitions': self.num_partitions
        }
        
        with open(output_file, 'w') as f:
            json.dump(boundary_data, f, indent=2)


def perform_verilog_partitioning(
    design_v: Path,
    part_file: Path,
    mapping_file: Path,
    output_dir: Path
) -> Dict:
    """
    执行Verilog分区（便利函数）
    
    Args:
        design_v: 原始门级网表
        part_file: K-SpecPart分区结果
        mapping_file: 映射文件
        output_dir: 输出目录
        
    Returns:
        分区结果字典
    """
    partitioner = VerilogPartitioner(design_v, part_file, mapping_file)
    return partitioner.partition(output_dir)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) < 5:
        print("用法: python verilog_partitioner.py <design.v> <part.4> <mapping.json> <output_dir>")
        sys.exit(1)
    
    result = perform_verilog_partitioning(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4])
    )
    
    print("\n分区完成！")
    print(f"Partition文件: {list(result['partition_files'].values())}")
    print(f"Top文件: {result['top_file']}")
    print(f"Boundary nets: {result['boundary_file']}")

