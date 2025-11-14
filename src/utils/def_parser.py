"""
DEF文件解析器
解析DEF文件，提取组件位置、网络连接等信息
"""

import re
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path


class DEFParser:
    """DEF文件解析器"""
    
    def __init__(self, def_file: str):
        """
        初始化DEF解析器
        
        Args:
            def_file: DEF文件路径
        """
        self.def_file = Path(def_file)
        self.units_per_micron = 1000  # 默认单位
        self.components: Dict[str, Dict[str, Any]] = {}
        self.nets: Dict[str, Dict[str, Any]] = {}
        self.die_area: Tuple[float, float, float, float] = (0, 0, 0, 0)
        
    def parse(self) -> Dict[str, Any]:
        """
        解析DEF文件
        
        Returns:
            解析结果字典
        """
        if not self.def_file.exists():
            raise FileNotFoundError(f"DEF文件不存在: {self.def_file}")
        
        with open(self.def_file, 'r') as f:
            content = f.read()
        
        # 解析单位
        self._parse_units(content)
        
        # 解析DIEAREA
        self._parse_die_area(content)
        
        # 解析COMPONENTS
        self._parse_components(content)
        
        # 解析NETS
        self._parse_nets(content)
        
        return {
            'units_per_micron': self.units_per_micron,
            'die_area': self.die_area,
            'components': self.components,
            'nets': self.nets
        }
    
    def _parse_units(self, content: str):
        """解析单位信息"""
        match = re.search(r'UNITS\s+DISTANCE\s+MICRONS\s+(\d+)', content)
        if match:
            self.units_per_micron = int(match.group(1))
    
    def _parse_die_area(self, content: str):
        """解析DIEAREA"""
        match = re.search(r'DIEAREA\s+\(\s*(\d+)\s+(\d+)\s+\)\s+\(\s*(\d+)\s+(\d+)\s+\)', content)
        if match:
            x1, y1, x2, y2 = map(int, match.groups())
            self.die_area = (x1, y1, x2, y2)
    
    def _parse_components(self, content: str):
        """解析COMPONENTS部分"""
        # 找到COMPONENTS部分
        comp_start = content.find('COMPONENTS')
        if comp_start == -1:
            return
        
        comp_end = content.find('END COMPONENTS', comp_start)
        if comp_end == -1:
            comp_end = content.find('NETS', comp_start)
        
        comp_section = content[comp_start:comp_end]
        
        # 解析每个组件
        # 格式可能包括：
        # - comp_name cell_name + PLACED ( x y ) orient ;
        # - comp_name cell_name + FIXED ( x y ) orient ;
        # - comp_name cell_name + UNPLACED ;
        # - comp_name cell_name + PLACED ( x y ) orient + REGION region_name ;
        # 注意：组件定义可能是多行的，+ UNPLACED可能在下一行
        
        # 使用更灵活的正则表达式，支持多行匹配
        # 匹配所有组件定义（包括多行格式）
        # 格式：- comp_name cell_name [换行] + STATUS [其他属性] ;
        comp_pattern = r'-\s+(\S+)\s+(\S+)(?:\s+|\s*\n\s*)\+\s+(UNPLACED|FIXED|PLACED)(?:\s+\(\s*(\d+)\s+(\d+)\s+\)\s+(\S+))?(?:\s+.*?)?\s*;'
        matches = re.finditer(comp_pattern, comp_section, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            comp_name = match.group(1)
            cell_name = match.group(2)
            status = match.group(3)  # UNPLACED, FIXED, or PLACED
            
            if status == 'UNPLACED':
                # UNPLACED组件没有位置信息，使用默认值
                if comp_name not in self.components:
                    self.components[comp_name] = {
                        'name': comp_name,
                        'cell': cell_name,
                        'x': 0,
                        'y': 0,
                        'orient': 'N',
                        'status': 'UNPLACED'
                    }
            else:
                # PLACED或FIXED组件有位置信息
                if match.group(4) and match.group(5) and match.group(6):
                    x = int(match.group(4))
                    y = int(match.group(5))
                    orient = match.group(6)
                    
                    self.components[comp_name] = {
                        'name': comp_name,
                        'cell': cell_name,
                        'x': x,
                        'y': y,
                        'orient': orient,
                        'status': status
                    }
                else:
                    # 如果位置信息缺失，使用默认值
                    self.components[comp_name] = {
                        'name': comp_name,
                        'cell': cell_name,
                        'x': 0,
                        'y': 0,
                        'orient': 'N',
                        'status': status
                    }
    
    def _parse_nets(self, content: str):
        """解析NETS部分"""
        # 找到NETS部分
        nets_start = content.find('NETS')
        if nets_start == -1:
            return
        
        nets_end = content.find('END NETS', nets_start)
        if nets_end == -1:
            nets_end = len(content)
        
        nets_section = content[nets_start:nets_end]
        
        # 解析每个net
        # 格式: - net_name ( comp_name pin_name ) ... ;
        net_pattern = r'-\s+(\S+)\s+(.*?)(?=\s+-\s+\S+|\s*END\s+NETS|$)'
        net_matches = re.finditer(net_pattern, nets_section, re.DOTALL)
        
        for net_match in net_matches:
            net_name = net_match.group(1)
            net_body = net_match.group(2)
            
            # 解析net中的连接
            pin_pattern = r'\(\s*(\S+)\s+(\S+)\s+\)'
            pin_matches = re.finditer(pin_pattern, net_body)
            
            connections = []
            for pin_match in pin_matches:
                comp_name = pin_match.group(1)
                pin_name = pin_match.group(2)
                connections.append({
                    'component': comp_name,
                    'pin': pin_name
                })
            
            if connections:
                self.nets[net_name] = {
                    'name': net_name,
                    'connections': connections
                }
    
    def get_component_position(self, comp_name: str) -> Optional[Tuple[float, float]]:
        """
        获取组件位置（转换为微米）
        
        Args:
            comp_name: 组件名称
        
        Returns:
            (x, y) 位置（微米），如果不存在返回None
        """
        if comp_name not in self.components:
            return None
        
        comp = self.components[comp_name]
        x_um = comp['x'] / self.units_per_micron
        y_um = comp['y'] / self.units_per_micron
        
        return (x_um, y_um)
    
    def get_net_connections(self, net_name: str) -> List[Dict[str, str]]:
        """
        获取net的连接信息
        
        Args:
            net_name: net名称
        
        Returns:
            连接列表
        """
        if net_name not in self.nets:
            return []
        
        return self.nets[net_name]['connections']
    
    def calculate_net_hpwl(self, net_name: str) -> float:
        """
        计算单个net的HPWL（半周线长）
        
        Args:
            net_name: net名称
        
        Returns:
            HPWL值（微米）
        """
        if net_name not in self.nets:
            return 0.0
        
        connections = self.nets[net_name]['connections']
        if len(connections) < 2:
            return 0.0
        
        # 获取所有连接点的位置
        positions = []
        for conn in connections:
            comp_name = conn['component']
            pos = self.get_component_position(comp_name)
            if pos is not None:
                positions.append(pos)
        
        if len(positions) < 2:
            return 0.0
        
        # 计算bounding box
        x_coords = [p[0] for p in positions]
        y_coords = [p[1] for p in positions]
        
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # HPWL = (x_max - x_min) + (y_max - y_min)
        hpwl = (x_max - x_min) + (y_max - y_min)
        
        return hpwl
    
    def calculate_total_hpwl(self) -> float:
        """
        计算总HPWL
        
        Returns:
            总HPWL值（微米）
        """
        total_hpwl = 0.0
        for net_name in self.nets:
            total_hpwl += self.calculate_net_hpwl(net_name)
        
        return total_hpwl
    
    def get_components_in_partition(
        self,
        partition_modules: List[str]
    ) -> List[str]:
        """
        获取分区中的组件列表
        
        Args:
            partition_modules: 分区模块列表（模块名可能对应组件名）
        
        Returns:
            组件名称列表
        """
        components = []
        for comp_name in self.components:
            # 检查组件是否属于分区中的模块
            # 这里假设组件名包含模块名，或模块名对应组件名
            for module_name in partition_modules:
                if module_name in comp_name or comp_name in module_name:
                    components.append(comp_name)
                    break
        
        return components
    
    def is_cross_partition_net(
        self,
        net_name: str,
        partition_scheme: Dict[str, List[str]]
    ) -> bool:
        """
        判断net是否跨分区
        
        Args:
            net_name: net名称
            partition_scheme: 分区方案
        
        Returns:
            是否跨分区
        """
        if net_name not in self.nets:
            return False
        
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        # 检查net连接的组件所属分区
        connections = self.nets[net_name]['connections']
        partitions_involved = set()
        
        for conn in connections:
            comp_name = conn['component']
            # 查找组件所属的分区
            for module_id, partition_id in module_to_partition.items():
                if module_id in comp_name or comp_name in module_id:
                    partitions_involved.add(partition_id)
                    break
        
        return len(partitions_involved) > 1

