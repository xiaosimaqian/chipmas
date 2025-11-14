"""
边界代价分析模块
识别跨分区连接、分解边界代价、计算边界代价
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import networkx as nx


class BoundaryAnalyzer:
    """边界代价分析器"""
    
    def __init__(self):
        """初始化边界分析器"""
        pass
    
    def count_cross_partition_connections(
        self,
        partition_scheme: Dict[str, List[str]],
        netlist: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        统计跨分区连接数
        
        Args:
            partition_scheme: 分区方案，格式为 {partition_id: [module_ids]}
            netlist: 网表信息，包含nets和modules
        
        Returns:
            统计结果字典：
                - total_nets: 总net数
                - cross_partition_nets: 跨分区net数
                - cross_partition_pins: 跨分区引脚数
                - net_cross_count: 每个net跨越的分区数
        """
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        # 统计跨分区连接
        total_nets = 0
        cross_partition_nets = 0
        cross_partition_pins = 0
        net_cross_count = {}
        
        if 'nets' in netlist:
            for net_id, net_info in netlist['nets'].items():
                total_nets += 1
                
                # 获取该net连接的所有模块
                connected_modules = set()
                if 'pins' in net_info:
                    for pin in net_info['pins']:
                        if 'module' in pin:
                            connected_modules.add(pin['module'])
                
                # 检查是否跨分区
                partitions_involved = set()
                for module_id in connected_modules:
                    if module_id in module_to_partition:
                        partitions_involved.add(module_to_partition[module_id])
                
                if len(partitions_involved) > 1:
                    cross_partition_nets += 1
                    cross_partition_pins += len(connected_modules)
                    net_cross_count[net_id] = len(partitions_involved)
        
        return {
            'total_nets': total_nets,
            'cross_partition_nets': cross_partition_nets,
            'cross_partition_pins': cross_partition_pins,
            'net_cross_count': net_cross_count
        }
    
    def decompose_boundary_cost(
        self,
        boundary_cost: float,
        partition_scheme: Dict[str, List[str]],
        netlist: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分解边界代价，分析各分区对边界代价的贡献
        
        Args:
            boundary_cost: 总边界代价
            partition_scheme: 分区方案
            netlist: 网表信息
        
        Returns:
            分解结果字典：
                - partition_contributions: 各分区对边界代价的贡献
                - boundary_module_contributions: 边界模块的贡献
                - net_contributions: 各net的贡献
        """
        # 统计跨分区连接
        cross_stats = self.count_cross_partition_connections(partition_scheme, netlist)
        
        # 计算各分区对边界代价的贡献（基于跨分区连接数和HPWL）
        partition_contributions = {}
        total_cross_pins = cross_stats['cross_partition_pins']
        
        if total_cross_pins > 0:
            for partition_id, module_ids in partition_scheme.items():
                # 计算该分区涉及的跨分区连接数
                partition_cross_pins = 0
                if 'nets' in netlist:
                    for net_id, net_info in netlist['nets'].items():
                        if net_id in cross_stats['net_cross_count']:
                            # 检查该net是否涉及此分区
                            if 'pins' in net_info:
                                for pin in net_info['pins']:
                                    if 'module' in pin and pin['module'] in module_ids:
                                        partition_cross_pins += 1
                                        break
                
                # 按比例分配边界代价
                if partition_cross_pins > 0:
                    contribution = (partition_cross_pins / total_cross_pins) * boundary_cost
                    partition_contributions[partition_id] = contribution
        
        return {
            'total_boundary_cost': boundary_cost,
            'partition_contributions': partition_contributions,
            'cross_partition_stats': cross_stats
        }
    
    def calculate_boundary_cost_from_def(
        self,
        def_file: str,
        partition_scheme: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        从DEF文件中计算边界代价
        
        Args:
            def_file: DEF文件路径
            partition_scheme: 分区方案
        
        Returns:
            边界代价相关指标：
                - boundary_cost: 边界代价百分比
                - total_hpwl: 总HPWL
                - partition_hpwls: 各分区内部HPWL
                - boundary_hpwl: 边界HPWL
        """
        from .def_parser import DEFParser
        
        # 解析DEF文件
        parser = DEFParser(def_file)
        parser.parse()
        
        # 计算总HPWL
        total_hpwl = parser.calculate_total_hpwl()
        
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        # 计算各分区内部HPWL（排除跨分区连接）
        partition_hpwls = {partition_id: 0.0 for partition_id in partition_scheme.keys()}
        
        for net_name, net_info in parser.nets.items():
            # 检查是否为跨分区net
            connections = net_info['connections']
            partitions_involved = set()
            
            for conn in connections:
                comp_name = conn['component']
                # 查找组件所属分区
                for module_id, partition_id in module_to_partition.items():
                    if module_id in comp_name or comp_name in module_id:
                        partitions_involved.add(partition_id)
                        break
            
            # 如果net只涉及一个分区，计入该分区的HPWL
            if len(partitions_involved) == 1:
                partition_id = list(partitions_involved)[0]
                net_hpwl = parser.calculate_net_hpwl(net_name)
                partition_hpwls[partition_id] += net_hpwl
        
        # 计算分区HPWL之和
        partition_hpwl_sum = sum(partition_hpwls.values())
        
        # 计算边界代价
        if partition_hpwl_sum > 0:
            boundary_cost = ((total_hpwl - partition_hpwl_sum) / partition_hpwl_sum) * 100.0
            boundary_hpwl = total_hpwl - partition_hpwl_sum
        else:
            boundary_cost = 0.0
            boundary_hpwl = 0.0
        
        return {
            'boundary_cost': boundary_cost,
            'total_hpwl': total_hpwl,
            'partition_hpwls': partition_hpwls,
            'boundary_hpwl': boundary_hpwl
        }
    
    def identify_boundary_modules(
        self,
        partition_scheme: Dict[str, List[str]],
        netlist: Dict[str, Any],
        threshold: float = 0.5
    ) -> Dict[str, List[str]]:
        """
        识别边界模块（高代价边界模块）
        
        Args:
            partition_scheme: 分区方案
            netlist: 网表信息
            threshold: 阈值（跨分区连接比例）
        
        Returns:
            各分区的边界模块列表 {partition_id: [boundary_module_ids]}
        """
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        # 统计每个模块的跨分区连接数
        module_cross_connections = {}
        module_total_connections = {}
        
        if 'nets' in netlist:
            for net_id, net_info in netlist['nets'].items():
                # 获取该net连接的所有模块
                connected_modules = []
                if 'pins' in net_info:
                    for pin in net_info['pins']:
                        if 'module' in pin:
                            connected_modules.append(pin['module'])
                
                # 检查是否跨分区
                partitions_involved = set()
                for module_id in connected_modules:
                    if module_id in module_to_partition:
                        partitions_involved.add(module_to_partition[module_id])
                
                if len(partitions_involved) > 1:
                    # 跨分区net，统计各模块的跨分区连接
                    for module_id in connected_modules:
                        if module_id in module_to_partition:
                            module_cross_connections[module_id] = \
                                module_cross_connections.get(module_id, 0) + 1
                
                # 统计总连接数
                for module_id in connected_modules:
                    if module_id in module_to_partition:
                        module_total_connections[module_id] = \
                            module_total_connections.get(module_id, 0) + 1
        
        # 识别边界模块（跨分区连接比例超过阈值）
        boundary_modules = {}
        for partition_id, module_ids in partition_scheme.items():
            partition_boundary = []
            for module_id in module_ids:
                cross_conn = module_cross_connections.get(module_id, 0)
                total_conn = module_total_connections.get(module_id, 0)
                
                if total_conn > 0:
                    cross_ratio = cross_conn / total_conn
                    if cross_ratio >= threshold:
                        partition_boundary.append(module_id)
            
            if partition_boundary:
                boundary_modules[partition_id] = partition_boundary
        
        return boundary_modules

