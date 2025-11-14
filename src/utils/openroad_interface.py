"""
OpenRoad接口模块
处理与OpenRoad的交互：分区约束转换、布局生成、HPWL计算
"""

import os
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from .def_parser import DEFParser


class OpenRoadInterface:
    """OpenRoad接口类"""
    
    def __init__(self, binary_path: str = "openroad", timeout: int = None, use_api: bool = True, threads: Optional[int] = None):
        """
        初始化OpenRoad接口
        
        Args:
            binary_path: OpenRoad可执行文件路径
            timeout: 超时时间（秒）。None或0表示不设置超时，等待OpenROAD自然完成（大设计可能需要数小时）
            use_api: 是否使用API（而非TCL命令）
            threads: OpenROAD线程数。None表示使用默认值，可以设置为数字或"max"（使用所有可用CPU核心）
                    注意：OpenROAD对内存要求高，建议不要同时运行多个OpenROAD进程
        """
        self.binary_path = binary_path
        # 如果timeout为None或0，表示不设置超时限制
        # 对于大设计，OpenROAD可能需要运行数小时，应该设置timeout=None或0
        self.timeout = timeout if timeout and timeout > 0 else None
        self.use_api = use_api
        self.threads = threads  # OpenROAD线程数
    
    def convert_partition_to_def_constraints(
        self,
        partition_scheme: Dict[str, List[str]],
        design_dir: str,
        output_def: Optional[str] = None
    ) -> str:
        """
        将ChipMASRAG分区方案转换为OpenRoad DEF约束
        
        详细说明：
        1. ChipMASRAG的分区方案基于模块（module），需要映射到DEF文件中的组件（component）
        2. 通过DEF文件的REGIONS和COMPONENTS部分，将分区方案转换为OpenROAD可识别的约束
        3. OpenROAD在placement时会考虑REGION约束，影响组件位置和最终HPWL
        
        转换过程：
        - 步骤1：解析DEF文件，提取所有组件
        - 步骤2：将模块映射到组件（通过组件名匹配或Verilog网表）
        - 步骤3：为每个分区创建REGION（GROUP类型）
        - 步骤4：在COMPONENTS部分为每个组件添加REGION属性
        - 步骤5：生成包含分区约束的新DEF文件
        
        Args:
            partition_scheme: 分区方案 {partition_id: [module_ids]}
            design_dir: 设计目录路径（包含floorplan.def）
            output_def: 输出DEF文件路径（如果为None，则自动生成）
        
        Returns:
            生成的DEF文件路径
        """
        design_path = Path(design_dir)
        input_def = design_path / "floorplan.def"
        
        if not input_def.exists():
            raise FileNotFoundError(f"找不到DEF文件: {input_def}")
        
        # 步骤1：解析DEF文件，提取所有组件
        parser = DEFParser(str(input_def))
        parser.parse()
        
        # 步骤2：构建模块到组件的映射
        # 方法：组件名包含模块名，或从Verilog网表提取（这里使用组件名匹配）
        module_to_components: Dict[str, List[str]] = {}
        component_to_partition: Dict[str, str] = {}
        
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                # 查找属于该模块的组件
                components = []
                for comp_name in parser.components.keys():
                    # 匹配规则：组件名包含模块名，或模块名包含在组件名中
                    if module_id in comp_name or comp_name.startswith(module_id):
                        components.append(comp_name)
                        component_to_partition[comp_name] = partition_id
                
                if module_id not in module_to_components:
                    module_to_components[module_id] = []
                module_to_components[module_id].extend(components)
        
        # 步骤3：读取原始DEF文件内容
        with open(input_def, 'r') as f:
            def_lines = f.readlines()
        
        if output_def is None:
            output_def = str(design_path / "floorplan_with_partition.def")
        
        # 步骤4：构建REGIONS部分和GROUPS部分
        # 根据DEF格式规范，需要同时有REGIONS部分（FENCE类型）和GROUPS部分
        # REGIONS格式：
        # REGIONS [number] ;
        #   - region_name ( x1 y1 ) ( x2 y2 ) ... + TYPE FENCE ;
        # END REGIONS
        # GROUPS格式：
        # GROUPS [number] ;
        #   - group_name comp1 comp2 comp3 ...
        #      + REGION region_name ;
        # END GROUPS
        
        # 读取die area（用于生成REGIONS）
        die_area = None
        for line in def_lines:
            if 'DIEAREA' in line:
                # 解析DIEAREA: DIEAREA ( x1 y1 ) ( x2 y2 ) ;
                import re
                match = re.search(r'DIEAREA\s+\(\s*(\d+)\s+(\d+)\s+\)\s+\(\s*(\d+)\s+(\d+)\s+\)', line)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    die_area = (x1, y1, x2, y2)
                break
        
        # 为每个分区收集所有组件
        partition_components: Dict[str, List[str]] = {}
        for partition_id in partition_scheme.keys():
            partition_components[partition_id] = []
        
        for comp_name, partition_id in component_to_partition.items():
            partition_components[partition_id].append(comp_name)
        
        # 生成REGIONS部分（FENCE类型）
        # 注意：根据成功案例mgc_pci_bridge32_a的观察，REGIONS必须存在且格式正确
        # GROUPS中的+ REGION属性会引用REGION名称，如果没有REGIONS定义会报错
        # 使用简单的2x2网格矩形格式（与成功案例一致），避免复杂多边形导致内存问题
        partition_id_to_index = {}
        sorted_partition_ids = sorted(partition_components.keys())
        for idx, pid in enumerate(sorted_partition_ids):
            partition_id_to_index[pid] = idx
        
        new_regions = []
        region_count = 0
        num_partitions = len([pid for pid in sorted_partition_ids if partition_components[pid]])
        
        # 计算每个REGION的边界（将die area分成不重叠的子区域）
        # 使用2x2网格布局，与成功案例mgc_pci_bridge32_a的格式一致
        if die_area:
            x1, y1, x2, y2 = die_area
            die_width = x2 - x1
            die_height = y2 - y1
        else:
            x1, y1, x2, y2 = 0, 0, 400000, 400000
            die_width = 400000
            die_height = 400000
        
        # 计算每个子区域的尺寸（2x2网格）
        region_width = die_width / 2
        region_height = die_height / 2
        
        for partition_id in sorted_partition_ids:
            comp_list = partition_components[partition_id]
            if not comp_list:
                continue  # 跳过空分区
            
            # 从partition_id中提取数字索引
            import re
            match = re.search(r'(\d+)$', str(partition_id))
            if match:
                partition_index = int(match.group(1))
            else:
                partition_index = partition_id_to_index.get(partition_id, region_count)
            
            region_name = f"er{partition_index}"
            region_count += 1
            
            # 根据partition_index计算子区域的位置（2x2网格）
            # partition_index 0: 左下 (0, 0)
            # partition_index 1: 右下 (1, 0)
            # partition_index 2: 左上 (0, 1)
            # partition_index 3: 右上 (1, 1)
            grid_x = partition_index % 2
            grid_y = partition_index // 2
            
            # 计算子区域的边界（留出边距避免完全重叠，与成功案例格式一致）
            margin = min(die_width, die_height) * 0.01  # 1%边距
            region_x1 = int(x1 + grid_x * region_width + margin)
            region_y1 = int(y1 + grid_y * region_height + margin)
            region_x2 = int(x1 + (grid_x + 1) * region_width - margin)
            region_y2 = int(y1 + (grid_y + 1) * region_height - margin)
            
            # 确保边界在die area内
            region_x1 = max(x1, region_x1)
            region_y1 = max(y1, region_y1)
            region_x2 = min(x2, region_x2)
            region_y2 = min(y2, region_y2)
            
            # 生成FENCE类型的REGION（简单矩形格式，与成功案例一致）
            region_def = f"   - {region_name}       ( {region_x1} {region_y1} ) ( {region_x2} {region_y2} )          + TYPE FENCE ;\n"
            new_regions.append(region_def)
        
        # 生成GROUPS部分
        new_groups = []
        group_count = 0
        # 将partition_id映射到数字索引
        partition_id_to_index = {}
        sorted_partition_ids = sorted(partition_components.keys())
        for idx, pid in enumerate(sorted_partition_ids):
            partition_id_to_index[pid] = idx
        
        for partition_id, comp_list in partition_components.items():
            if not comp_list:
                continue  # 跳过空分区
            
            # 从partition_id中提取数字索引（如"partition_0" -> 0, "partition_1" -> 1）
            # 或者如果partition_id本身就是数字，直接使用
            import re
            match = re.search(r'(\d+)$', str(partition_id))
            if match:
                partition_index = int(match.group(1))
            else:
                # 如果无法提取数字，使用映射的索引
                partition_index = partition_id_to_index.get(partition_id, group_count)
            
            group_name = f"er{partition_index}"  # 使用er0, er1, er2等格式
            region_name = f"er{partition_index}"  # REGION名称与group名称相同
            group_count += 1
            
            # GROUPS格式（参考floorplan.def）：
            #   - group_name comp1 comp2 comp3 ...  (3个空格缩进)
            #      + REGION region_name ;           (6个空格缩进)
            # 如果组件列表太长，分行写入（每行最多10个组件，避免行过长）
            if len(comp_list) > 10:
                # 分行格式：第一行3个空格缩进，后续行6个空格缩进
                group_def = f"   - {group_name} "
                # 第一行添加前几个组件
                first_batch = comp_list[:10]
                group_def += " ".join(first_batch) + "\n"
                # 后续行每行10个组件，缩进6个空格（与REGION属性对齐）
                for j in range(10, len(comp_list), 10):
                    batch = comp_list[j:j+10]
                    group_def += f"      {' '.join(batch)}\n"
                # 添加REGION属性（6个空格缩进）
                group_def += f"      + REGION {region_name} ;\n"
            else:
                # 单行格式（3个空格缩进）
                comp_list_str = " ".join(comp_list)
                group_def = f"   - {group_name} {comp_list_str}\n"
                # REGION属性（6个空格缩进）
                group_def += f"      + REGION {region_name} ;\n"
            new_groups.append(group_def)
        
        # 步骤5：处理DEF文件，插入REGIONS和GROUPS部分
        # 注意：不在COMPONENTS中添加+ REGION属性，而是使用REGIONS和GROUPS部分
        # REGIONS应该在COMPONENTS之前，GROUPS应该在END COMPONENTS之后（或在END NETS之后）
        output_lines = []
        in_regions_section = False
        in_groups_section = False
        regions_inserted = False
        groups_inserted = False
        has_existing_regions = False
        has_existing_groups = False
        
        # 先检查是否已有REGIONS和GROUPS部分
        for line in def_lines:
            if line.strip().startswith('REGIONS'):
                has_existing_regions = True
            if line.strip().startswith('GROUPS'):
                has_existing_groups = True
        
        i = 0
        while i < len(def_lines):
            line = def_lines[i]
            
            # 检查是否进入REGIONS部分（在COMPONENTS之前）
            if line.strip().startswith('REGIONS') and not regions_inserted:
                in_regions_section = True
                # 跳过现有的REGIONS部分，稍后替换
                i += 1
                continue
            
            # 检查是否离开REGIONS部分
            if line.strip().startswith('END REGIONS') and in_regions_section:
                in_regions_section = False
                # 插入新的REGIONS部分（在COMPONENTS之前）
                if new_regions:
                    if region_count > 0:
                        output_lines.append(f"REGIONS {region_count} ;\n")
                    else:
                        output_lines.append("REGIONS ;\n")
                    output_lines.extend(new_regions)
                    output_lines.append("END REGIONS\n")
                    regions_inserted = True
                i += 1
                continue
            
            # 如果在REGIONS部分内，跳过（稍后替换）
            if in_regions_section:
                i += 1
                continue
            
            # 检查是否进入COMPONENTS部分（如果REGIONS还没有插入，在这里插入）
            if line.strip().startswith('COMPONENTS') and not regions_inserted and new_regions:
                # 在COMPONENTS之前插入REGIONS
                if region_count > 0:
                    output_lines.append(f"REGIONS {region_count} ;\n")
                else:
                    output_lines.append("REGIONS ;\n")
                output_lines.extend(new_regions)
                output_lines.append("END REGIONS\n")
                regions_inserted = True
                output_lines.append(line)
                i += 1
                continue
            
            # 检查是否离开COMPONENTS部分
            if line.strip().startswith('END COMPONENTS'):
                output_lines.append(line)
                i += 1
                continue
            
            # 检查是否进入GROUPS部分（在END COMPONENTS或END NETS之后）
            # 注意：如果已经插入过GROUPS，遇到新的GROUPS部分时应该跳过（可能是重复的）
            if line.strip().startswith('GROUPS'):
                if not groups_inserted:
                    # 第一次遇到GROUPS，标记为在GROUPS部分内，稍后替换
                    in_groups_section = True
                    i += 1
                    continue
                else:
                    # 已经插入过GROUPS，这是重复的GROUPS部分，完全跳过
                    in_groups_section = True
                    i += 1
                    continue
            
            # 检查是否离开GROUPS部分
            if line.strip().startswith('END GROUPS') and in_groups_section:
                in_groups_section = False
                # 只在第一次遇到END GROUPS时插入新的GROUPS部分
                if not groups_inserted and new_groups:
                    if group_count > 0:
                        output_lines.append(f"GROUPS {group_count} ;\n")
                    else:
                        output_lines.append("GROUPS ;\n")
                    output_lines.extend(new_groups)
                    output_lines.append("END GROUPS\n")
                    groups_inserted = True
                # 无论是否插入，都跳过END GROUPS行（避免重复）
                i += 1
                continue
            
            # 如果在GROUPS部分内，跳过（稍后替换或完全忽略）
            if in_groups_section:
                i += 1
                continue
            
            # 检查是否在END NETS之后（GROUPS应该在这里）
            if line.strip().startswith('END NETS'):
                output_lines.append(line)
                i += 1
                # 在END NETS之后插入GROUPS（如果还没有插入）
                if not groups_inserted and new_groups:
                    if group_count > 0:
                        output_lines.append(f"GROUPS {group_count} ;\n")
                    else:
                        output_lines.append("GROUPS ;\n")
                    output_lines.extend(new_groups)
                    output_lines.append("END GROUPS\n")
                    groups_inserted = True
                continue
            
            output_lines.append(line)
            i += 1
        
        # 如果还没有插入REGIONS（例如DEF文件没有COMPONENTS部分），在文件末尾添加
        if not regions_inserted and new_regions:
            if region_count > 0:
                output_lines.append(f"REGIONS {region_count} ;\n")
            else:
                output_lines.append("REGIONS ;\n")
            output_lines.extend(new_regions)
            output_lines.append("END REGIONS\n")
        
        # 如果还没有插入GROUPS（例如DEF文件没有END NETS部分），在文件末尾添加
        if not groups_inserted and new_groups:
            if group_count > 0:
                output_lines.append(f"GROUPS {group_count} ;\n")
            else:
                output_lines.append("GROUPS ;\n")
            output_lines.extend(new_groups)
            output_lines.append("END GROUPS\n")
        
        # 步骤6：写入新的DEF文件
        with open(output_def, 'w') as f:
            f.writelines(output_lines)
        
        # 注意：partition netlist的保存应该在generate_layout_with_partition中统一处理
        # 这里不保存，避免重复调用和路径不一致问题
        
        return output_def
    
    def generate_layout_with_partition(
        self,
        partition_scheme: Dict[str, List[str]],
        design_dir: str,
        output_dir: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        使用OpenRoad根据分区方案生成布局
        
        Args:
            partition_scheme: 分区方案
            design_dir: 设计目录路径
            output_dir: 输出目录（如果为None，则在design_dir下创建）
        
        Returns:
            (布局DEF文件路径, 布局信息字典)
        """
        design_path = Path(design_dir)
        
        # 1. 转换分区方案为DEF约束
        def_with_partition = self.convert_partition_to_def_constraints(
            partition_scheme, design_dir
        )
        
        # 2. 确定输出DEF文件路径
        # 默认输出到results目录，而不是原始数据集目录
        if output_dir is None:
            # 获取项目根目录（假设design_dir在data/ispd2015/xxx下）
            # 向上查找，找到包含data目录的根目录
            current = design_path
            project_root = None
            while current != current.parent:
                if (current / "data").exists() and (current / "src").exists():
                    project_root = current
                    break
                current = current.parent
            
            if project_root is None:
                # 如果找不到项目根目录，使用design_dir的相对路径
                project_root = design_path.parent.parent.parent  # 假设是data/ispd2015/xxx
            
            # 创建results目录结构：results/ispd2015/design_name/
            design_name = design_path.name
            benchmark_name = design_path.parent.name  # ispd2015
            output_dir = str(project_root / "results" / benchmark_name / design_name)
        else:
            output_dir = str(Path(output_dir))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳命名layout.def，与日志文件命名保持一致
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_def = str(Path(output_dir) / f"layout_{timestamp}.def")
        
        # 1.5. 保存partition netlist（与DEF文件中的分区信息一致）
        # 保存在与log、layout.def相同的目录下，使用时间戳区分版本
        partition_netlists = self.save_partition_netlists(
            partition_scheme=partition_scheme,
            design_dir=design_dir,
            output_dir=output_dir,
            timestamp=timestamp
        )
        
        # 3. 生成OpenRoad TCL脚本（包含输出路径）
        tcl_script = self._generate_tcl_script(design_path, def_with_partition, output_def)
        
        # 4. 执行OpenRoad
        layout_def, layout_info = self._run_openroad(tcl_script, output_dir)
        
        return layout_def, layout_info
    
    def _generate_tcl_script(
        self,
        design_path: Path,
        def_file: str,
        output_def: Optional[str] = None
    ) -> str:
        """
        生成OpenRoad TCL脚本
        
        根据OpenRoad官方文档，完整的布局流程包括：
        - ifp: Initialize Floorplan (https://openroad.readthedocs.io/en/latest/main/src/ifp/README.html)
        - ppl: Pin Placement (https://openroad.readthedocs.io/en/latest/main/src/ppl/README.html)
        - mpl: Macro Placement (https://openroad.readthedocs.io/en/latest/main/src/mpl/README.html)
        - gpl: Global Placement (https://openroad.readthedocs.io/en/latest/main/src/gpl/README.html)
        - dpl: Detailed Placement (https://openroad.readthedocs.io/en/latest/main/src/dpl/README.html)
        
        注意：legalized HPWL数据是在detailed placement过程中报告出的
        
        Args:
            design_path: 设计目录路径
            def_file: 包含分区约束的DEF文件路径
            output_def: 输出DEF文件路径（如果为None，则在脚本中不指定，由调用者添加）
        
        Returns:
            TCL脚本路径
        """
        # 使用绝对路径，避免相对路径问题
        # 注意：resolve()会在当前运行环境中解析路径，确保使用服务器上的实际路径
        # 如果design_path是相对路径，先转换为绝对路径
        if not design_path.is_absolute():
            # 如果design_path是相对路径，需要基于当前工作目录解析
            # 但更好的方法是确保传入的design_path已经是绝对路径
            design_path = design_path.resolve()
        else:
            # 如果已经是绝对路径，直接使用（但需要确保路径存在）
            design_path = Path(design_path)
        
        tech_lef = (design_path / "tech.lef").resolve()
        cells_lef = (design_path / "cells.lef").resolve()
        def_path = Path(def_file).resolve()
        design_path_str = str(design_path.resolve())
        design_v = (design_path / "design.v").resolve()
        
        # 参考成功案例（dreamplace_experiment/chipkag）：不读 floorplan.def，直接使用 initialize_floorplan
        # 从参考成功案例中提取的 die size 配置，每个设计可能有不同的 die size
        # 这样可以避免从 floorplan.def 读取过大的 die size 导致 OOM
        # 
        # 注意：如果 def_file 是 floorplan_with_partition.def（包含分区约束），
        # 我们需要在 link_design 之后读取它来应用分区约束，但不用于初始化 floorplan
        
        # 从 def_file 中读取设计名（用于 link_design 和查找 die size）
        # 如果 def_file 是 floorplan_with_partition.def，从中读取设计名
        design_name = None
        try:
            with open(def_path, 'r') as f:
                def_content = f.read()
                # 读取设计名
                for line in def_content.split('\n'):
                    if line.strip().startswith('DESIGN'):
                        # 格式：DESIGN design_name ;
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            design_name = parts[1].rstrip(';')
                        break
        except Exception:
            pass
        
        # 如果无法从 def_file 读取设计名，尝试从原始 floorplan.def 或目录名读取
        if design_name is None:
            try:
                with open(design_path / "floorplan.def", 'r') as f:
                    for line in f:
                        if line.strip().startswith('DESIGN'):
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                design_name = parts[1].rstrip(';')
                            break
            except Exception:
                pass
        
        # 如果还是无法读取，使用目录名作为设计名
        if design_name is None:
            design_name = design_path.name
        
        # 从配置中获取 die size（根据设计名）
        try:
            from .die_size_config import get_die_size
            die_area_str, core_area_str = get_die_size(design_name)
        except (ImportError, Exception) as e:
            # 如果导入失败或设计不在配置中，使用默认值
            die_area_str = "0 0 5000 5000"
            core_area_str = "250 250 4750 4750"
        
        # 构建TCL脚本内容
        # 完整的OpenRoad布局流程（根据OpenROAD User Guide）
        # 参考：https://openroad.readthedocs.io/en/latest/main/README2.html
        # 参考成功案例：chipLLM/experiments/archive_20251111_185539/boundary_experiments_20251110/mgc_pci_bridge32_a_20251110_144208/mgc_pci_bridge32_a_placement.tcl
        # 关键点：
        # 1. 先读取tech.lef，再读取cells.lef（使用read_lef，不带-tech/-library参数）
        # 2. 直接读取DEF文件（不需要read_verilog或link_design）
        # 3. 如果DEF文件包含ROWS，OpenROAD会自动识别，不需要initialize_floorplan
        # 4. 使用global_placement -skip_initial_place，然后detailed_placement
        # 注意：使用普通字符串模板，避免f-string中的{{}}与format()冲突
        tcl_content = """# OpenRoad TCL脚本 - 完整的布局流程
# 基于OpenRoad官方文档：
# - User Guide: https://openroad.readthedocs.io/en/latest/main/README2.html
# - ifp: https://openroad.readthedocs.io/en/latest/main/src/ifp/README.html
# - ppl: https://openroad.readthedocs.io/en/latest/main/src/ppl/README.html
# - mpl: https://openroad.readthedocs.io/en/latest/main/src/mpl/README.html
# - gpl: https://openroad.readthedocs.io/en/latest/main/src/gpl/README.html
# - dpl: https://openroad.readthedocs.io/en/latest/main/src/dpl/README.html

# ============================================
# 步骤1: 读取LEF文件
# ============================================
# 先读取tech.lef（技术文件，必须先读取）
read_lef {tech_lef}

# 再读取cells.lef（标准单元库）
read_lef {cells_lef}

# ============================================
# 步骤2: 读取Verilog网表（如果存在）
# ============================================
# 参考成功案例：先读取 Verilog，然后 link_design
set verilog_file {design_path_str}/design.v
if {{[file exists $verilog_file]}} {{
    read_verilog $verilog_file
}}

# ============================================
# 步骤3: 链接设计（必需，在初始化 floorplan 之前）
# ============================================
# 参考成功案例：在读取 DEF 之前先 link_design
if {{[file exists $verilog_file]}} {{
    link_design {design_name}
}}

# ============================================
# 步骤4: 初始化Floorplan（参考成功案例，不读 floorplan.def）
# ============================================
# 参考成功案例：直接使用 initialize_floorplan，不读取 floorplan.def
# 这样可以避免从 floorplan.def 读取过大的 die size 导致 OOM
# 未来改进：从知识库检索合理的 die size
initialize_floorplan -die_area "{die_area_str}" -core_area "{core_area_str}" -site core

# 生成轨道
make_tracks

# ============================================
# 步骤5: 读取DEF文件（仅当包含分区约束时）
# ============================================
# 注意：如果 def_file 是 floorplan_with_partition.def（包含分区约束），
# 需要在 initialize_floorplan 之后读取来应用分区约束
# 但如果只是普通的 floorplan.def，不读取（因为已经用 initialize_floorplan 初始化了）
# 检查文件名是否包含 "partition" 关键字
set def_file_name {def_path}
if {{[string match "*partition*" $def_file_name]}} {{
    # 如果包含 partition，尝试读取分区约束
    if {{[catch {{
        read_def {def_path}
    }} err]}} {{
        # 如果读取失败，继续执行（分区约束可能已经在其他地方应用）
        # 错误信息会被忽略
    }}
}} else {{
    # 如果是普通的 floorplan.def，不读取（避免 Chip already exists 错误）
    # 因为已经用 initialize_floorplan 初始化了
}}

# ============================================
# 步骤4: 放置顶层端口（PINS）
# ============================================
# 必须在global placement之前放置顶层端口
# 如果DEF文件中的PINS已经有位置（+ PLACED），则不需要place_pins
# 但如果PINS没有位置，必须调用place_pins
# 使用catch来尝试place_pins，如果失败说明PINS已有位置
if {{[catch {{
    place_pins -hor_layers metal3 -ver_layers metal2
}} err]}} {{
    # 如果place_pins失败，尝试不带参数（使用默认参数）
    if {{[catch {{
        place_pins
    }} err2]}} {{
        # 如果还是失败，说明PINS可能已有位置或不需要放置
        # 继续执行，不中断流程
    }}
}}

# ============================================
# 步骤5: 设置placement参数（可选）
# ============================================
# 设置placement padding（可选，参考案例中有此设置）
set_placement_padding -global -left 2 -right 2

# ============================================
# 步骤6: Global Placement (gpl)
# ============================================
# 全局布局：将标准单元放置在芯片上
# 使用-skip_initial_place参数（参考成功案例）
global_placement -skip_initial_place

# ============================================
# 步骤7: Detailed Placement (dpl)
# ============================================
# 详细布局（legalization）：确保所有单元都放置在合法位置
# 注意：legalized HPWL数据是在detailed placement过程中报告出的
detailed_placement

# ============================================
# 步骤8: 报告HPWL
# ============================================
# HPWL信息会在detailed placement的输出中自动报告
# 可以通过解析stdout/stderr获取HPWL值
"""
        
        # 如果未找到设计名，使用默认值（从DEF文件名提取）
        if design_name is None:
            design_name = design_path.name
        
        # 替换TCL脚本中的占位符（先替换基本占位符）
        tcl_content = tcl_content.format(
            tech_lef=str(tech_lef),
            cells_lef=str(cells_lef),
            def_path=str(def_path),
            design_path_str=design_path_str,
            die_area_str=die_area_str,
            core_area_str=core_area_str,
            design_name=design_name
        )
        
        # 如果指定了输出DEF文件，添加write_def命令（在format之后添加，避免占位符冲突）
        if output_def:
            output_def_path = Path(output_def).resolve()
            tcl_content += f"""
# 输出最终布局DEF文件
write_def {output_def_path}
"""
        
        # 保存TCL脚本
        tcl_file = design_path / "openroad_script.tcl"
        with open(tcl_file, 'w') as f:
            f.write(tcl_content)
        
        return str(tcl_file)
    
    def _run_openroad(
        self,
        tcl_script: str,
        output_dir: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        执行OpenRoad TCL脚本
        
        Args:
            tcl_script: TCL脚本路径
            output_dir: 输出目录
        
        Returns:
            (布局DEF文件路径, 布局信息)
        """
        tcl_path = Path(tcl_script)
        script_dir = tcl_path.parent
        
        if output_dir is None:
            output_dir = str(script_dir / "openroad_output")
        else:
            output_dir = str(Path(output_dir))
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 设置日志文件路径
        log_dir = Path(output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        stdout_log = log_dir / f"openroad_stdout_{timestamp}.log"
        stderr_log = log_dir / f"openroad_stderr_{timestamp}.log"
        combined_log = log_dir / f"openroad_combined_{timestamp}.log"
        
        # 读取TCL脚本内容（已经包含write_def命令）
        with open(tcl_script, 'r') as f:
            tcl_content = f.read()
        
        # 检查TCL脚本是否包含write_def命令
        # 如果没有，从脚本中提取输出路径或使用默认路径（使用时间戳命名）
        if 'write_def' not in tcl_content:
            # 使用时间戳命名，与日志文件命名保持一致
            output_def = str(Path(output_dir) / f"layout_{timestamp}.def")
            tcl_content += f"\nwrite_def {output_def}\n"
            # 保存修改后的TCL脚本
            modified_tcl = str(script_dir / "openroad_script_modified.tcl")
            with open(modified_tcl, 'w') as f:
                f.write(tcl_content)
            tcl_script = modified_tcl
        else:
            # 从TCL脚本中提取输出DEF路径
            import re
            match = re.search(r'write_def\s+(\S+)', tcl_content)
            if match:
                output_def = match.group(1)
                # 如果提取的路径是默认的layout.def，改为使用时间戳命名
                if output_def.endswith('/layout.def') or output_def.endswith('\\layout.def'):
                    output_def = str(Path(output_dir) / f"layout_{timestamp}.def")
                    # 更新TCL脚本中的路径
                    tcl_content = re.sub(
                        r'write_def\s+\S+',
                        f'write_def {output_def}',
                        tcl_content
                    )
                    modified_tcl = str(script_dir / "openroad_script_modified.tcl")
                    with open(modified_tcl, 'w') as f:
                        f.write(tcl_content)
                    tcl_script = modified_tcl
            else:
                # 使用时间戳命名，与日志文件命名保持一致
                output_def = str(Path(output_dir) / f"layout_{timestamp}.def")
        
        # 执行OpenRoad
        # 根据OpenRoad文档：https://openroad.readthedocs.io/en/latest/main/src/README.html
        # 可以使用 `source` 命令执行TCL脚本
        # 注意：需要参考远程服务器上成功运行的TCL命令格式
        start_time = time.time()
        try:
            tcl_script_abs = Path(tcl_script).resolve()
            
            # 方法1：尝试使用source命令（通过stdin）
            # 根据OpenRoad文档，可以使用source命令执行脚本
            # 注意：OpenROAD可能需要完整的TCL命令序列，包括exit命令
            
            # 读取TCL脚本内容并直接执行（而不是source命令）
            # 这样可以避免路径问题
            with open(tcl_script, 'r') as f:
                tcl_script_content = f.read()
            
            # 构建完整的TCL命令序列：脚本内容 + exit
            tcl_commands = f"{tcl_script_content}\nexit\n"
            
            # 打开日志文件用于实时写入
            stdout_file = open(stdout_log, 'w', buffering=1)  # 行缓冲
            stderr_file = open(stderr_log, 'w', buffering=1)  # 行缓冲
            combined_file = open(combined_log, 'w', buffering=1)  # 行缓冲
            
            # 写入日志文件头部（包含有用的信息）
            timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
            combined_file.write("="*80 + "\n")
            combined_file.write("OpenROAD Execution Log\n")
            combined_file.write(f"Timestamp: {timestamp_str}\n")
            combined_file.write(f"TCL Script: {tcl_script}\n")
            combined_file.write(f"Output DEF: {output_def}\n")
            combined_file.write("="*80 + "\n\n")
            combined_file.write("STDOUT:\n")
            combined_file.write("-"*80 + "\n")
            combined_file.flush()
            
            # 同时在stdout和stderr日志文件中也写入头部信息
            stdout_file.write(f"# OpenROAD Execution Log\n")
            stdout_file.write(f"# Timestamp: {timestamp_str}\n")
            stdout_file.write(f"# TCL Script: {tcl_script}\n")
            stdout_file.write(f"# Output DEF: {output_def}\n")
            stdout_file.write(f"# {'='*76}\n\n")
            stdout_file.flush()
            
            stderr_file.write(f"# OpenROAD Execution Log (STDERR)\n")
            stderr_file.write(f"# Timestamp: {timestamp_str}\n")
            stderr_file.write(f"# TCL Script: {tcl_script}\n")
            stderr_file.write(f"# Output DEF: {output_def}\n")
            stderr_file.write(f"# {'='*76}\n\n")
            stderr_file.flush()
            
            # 构建OpenROAD命令（添加线程参数）
            openroad_cmd = [self.binary_path]
            if self.threads is not None:
                if self.threads == "max" or str(self.threads).lower() == "max":
                    openroad_cmd.extend(["-threads", "max"])
                else:
                    try:
                        thread_count = int(self.threads)
                        openroad_cmd.extend(["-threads", str(thread_count)])
                    except (ValueError, TypeError):
                        # 如果threads参数无效，忽略它
                        pass
            
            process = subprocess.Popen(
                openroad_cmd,
                cwd=script_dir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                errors='replace'  # 处理编码错误：用替换字符代替无法解码的字节
            )
            
            # 实时读取并写入日志
            import threading
            import queue
            
            stdout_queue = queue.Queue()
            stderr_queue = queue.Queue()
            stdout_lines = []
            stderr_lines = []
            
            def read_stdout():
                """实时读取stdout并写入文件"""
                for line in process.stdout:
                    stdout_queue.put(line)
                    stdout_lines.append(line)
                    stdout_file.write(line)
                    stdout_file.flush()
                    combined_file.write(line)
                    combined_file.flush()
                stdout_queue.put(None)  # 结束标记
            
            def read_stderr():
                """实时读取stderr并写入文件"""
                for line in process.stderr:
                    stderr_queue.put(line)
                    stderr_lines.append(line)
                    stderr_file.write(line)
                    stderr_file.flush()
                    # stderr也会写入combined，但标记为STDERR部分
                    # 这里先不写，等stdout结束后再写
            
            # 启动读取线程
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            
            # 发送TCL命令到stdin
            process.stdin.write(tcl_commands)
            process.stdin.close()
            
            # 等待进程完成
            if self.timeout is None:
                process.wait()
            else:
                try:
                    process.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    # 超时处理在后面的except块中
                    raise
            
            # 等待读取线程完成
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            # 写入stderr到combined文件
            combined_file.write("\n\n" + "="*80 + "\n")
            combined_file.write("STDERR:\n")
            combined_file.write("-"*80 + "\n")
            for line in stderr_lines:
                combined_file.write(line)
            combined_file.flush()
            
            # 关闭日志文件
            stdout_file.close()
            stderr_file.close()
            combined_file.close()
            
            # 合并输出为字符串（用于后续处理）
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            # 创建类似subprocess.run的结果对象
            class Result:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr
            
            result = Result(process.returncode, stdout, stderr)
            
            runtime = time.time() - start_time
            
            # 检查stdout中是否有严重错误信息
            # 注意：某些 ERROR 信息（如 "Chip already exists"）被 catch 捕获，不影响最终结果
            # 如果 exit code 是 0 且生成了输出 DEF 文件，应该认为是成功的
            output_text = result.stdout + "\n" + result.stderr
            
            # 检查是否有严重错误（排除被 catch 捕获的已知错误）
            critical_errors = ['fatal', 'cannot', 'unable', 'invalid', 'segmentation fault', 'core dumped']
            has_critical_error = any(keyword in output_text.lower() for keyword in critical_errors)
            
            # 如果 exit code 是 0 且生成了输出 DEF 文件，即使有一些 ERROR 信息也认为是成功的
            if result.returncode == 0 and Path(output_def).exists():
                # 成功：即使有一些非关键错误信息
                pass
            elif result.returncode == 0 and not has_critical_error:
                # 成功：没有严重错误
                pass
            else:
                # 失败：有严重错误或 exit code 非 0
                has_critical_error = True
            
            if result.returncode == 0 and not has_critical_error:
                # 检查输出DEF文件是否存在
                if Path(output_def).exists():
                    # 从detailed placement的输出中提取HPWL
                    # legalized HPWL数据是在detailed placement过程中报告出的
                    hpwl = self._extract_hpwl_from_output(result.stdout, result.stderr)
                    
                    layout_info = {
                        'status': 'success',
                        'hpwl': hpwl,  # 从detailed placement输出中提取
                        'runtime': runtime,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'log_files': {
                            'stdout': str(stdout_log),
                            'stderr': str(stderr_log),
                            'combined': str(combined_log)
                        }
                    }
                    return output_def, layout_info
                else:
                    # 输出文件不存在，检查是否有错误信息
                    error_msg = 'Output DEF file not generated'
                    
                    # 从输出中提取错误和警告信息
                    error_lines = []
                    warning_lines = []
                    for line in output_text.split('\n'):
                        line_lower = line.lower()
                        if any(kw in line_lower for kw in ['error', 'failed', 'fatal', 'cannot', 'unable', 'invalid']):
                            if 'error' in line_lower or 'failed' in line_lower or 'fatal' in line_lower:
                                error_lines.append(line.strip())
                        elif 'warning' in line_lower:
                            warning_lines.append(line.strip())
                    
                    if error_lines:
                        error_msg += f". Errors found: {'; '.join(error_lines[:5])}"
                    elif warning_lines:
                        error_msg += f". Warnings (may indicate issues): {'; '.join(warning_lines[:3])}"
                    else:
                        # 检查stdout的最后几行，看看执行到哪里了
                        stdout_lines = result.stdout.split('\n')
                        last_lines = stdout_lines[-10:] if len(stdout_lines) > 10 else stdout_lines
                        error_msg += f". Last output lines: {'; '.join([l.strip() for l in last_lines if l.strip()][-3:])}"
                    
                    layout_info = {
                        'status': 'error',
                        'error': error_msg,
                        'runtime': runtime,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'output_file_expected': output_def,
                        'has_errors': len(error_lines) > 0,
                        'has_warnings': len(warning_lines) > 0,
                        'log_files': {
                            'stdout': str(stdout_log),
                            'stderr': str(stderr_log),
                            'combined': str(combined_log)
                        }
                    }
                    return "", layout_info
            else:
                # 根据返回码提供更详细的错误信息
                if result.returncode == -9:
                    # 返回码 -9 表示进程被 SIGKILL 强制终止
                    error_msg = (
                        f'OpenRoad execution failed with code {result.returncode} (SIGKILL). '
                        f'This usually indicates:\n'
                        f'  1. Out of Memory (OOM Killer terminated the process)\n'
                        f'  2. System resource limits (ulimit)\n'
                        f'  3. Manual termination (kill -9)\n'
                        f'  Runtime: {runtime:.2f}s\n'
                        f'  Check system logs (dmesg or /var/log/syslog) for OOM messages.'
                    )
                elif result.returncode < 0:
                    # 负返回码通常表示进程被信号终止
                    signal_num = -result.returncode
                    error_msg = (
                        f'OpenRoad execution failed with code {result.returncode} '
                        f'(terminated by signal {signal_num}). '
                        f'Runtime: {runtime:.2f}s'
                    )
                else:
                    # 正返回码表示程序正常退出但返回错误
                    error_msg = (
                        f'OpenRoad execution failed with code {result.returncode}. '
                        f'Runtime: {runtime:.2f}s'
                    )
                
                # 尝试从输出中提取更多错误信息
                output_text = result.stdout + "\n" + result.stderr
                error_lines = []
                warning_lines = []
                for line in output_text.split('\n'):
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in ['error', 'failed', 'fatal', 'cannot', 'unable', 'invalid', 'killed', 'oom']):
                        if 'error' in line_lower or 'failed' in line_lower or 'fatal' in line_lower or 'killed' in line_lower or 'oom' in line_lower:
                            error_lines.append(line.strip())
                    elif 'warning' in line_lower:
                        warning_lines.append(line.strip())
                
                if error_lines:
                    error_msg += f"\n  Errors in output: {'; '.join(error_lines[:5])}"
                if warning_lines:
                    error_msg += f"\n  Warnings: {'; '.join(warning_lines[:3])}"
                
                # 检查stdout的最后几行
                stdout_lines = result.stdout.split('\n')
                last_lines = stdout_lines[-10:] if len(stdout_lines) > 10 else stdout_lines
                last_non_empty = [l.strip() for l in last_lines if l.strip()]
                if last_non_empty:
                    error_msg += f"\n  Last output lines: {'; '.join(last_non_empty[-3:])}"
                
                layout_info = {
                    'status': 'error',
                    'error': error_msg,
                    'returncode': result.returncode,
                    'runtime': runtime,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'log_files': {
                        'stdout': str(stdout_log),
                        'stderr': str(stderr_log),
                        'combined': str(combined_log)
                    }
                }
                return "", layout_info
                
        except subprocess.TimeoutExpired:
            # 超时后不终止进程，让OpenROAD继续在后台运行
            # 注意：进程仍在运行，用户需要手动检查结果
            # 确保日志文件已关闭
            try:
                if 'stdout_file' in locals():
                    stdout_file.close()
                if 'stderr_file' in locals():
                    stderr_file.close()
                if 'combined_file' in locals():
                    combined_file.close()
            except:
                pass
            
            runtime = time.time() - start_time
            layout_info = {
                'status': 'timeout',
                'error': f'OpenRoad execution timeout after {self.timeout}s (process still running)',
                'runtime': runtime,
                'process_id': process.pid if 'process' in locals() else None,
                'note': 'OpenROAD process is still running in the background. Check the output DEF file later.',
                'log_files': {
                    'stdout': str(stdout_log) if 'stdout_log' in locals() else None,
                    'stderr': str(stderr_log) if 'stderr_log' in locals() else None,
                    'combined': str(combined_log) if 'combined_log' in locals() else None
                }
            }
            return "", layout_info
        except Exception as e:
            # 确保日志文件已关闭
            try:
                if 'stdout_file' in locals():
                    stdout_file.close()
                if 'stderr_file' in locals():
                    stderr_file.close()
                if 'combined_file' in locals():
                    combined_file.close()
            except:
                pass
            
            layout_info = {
                'status': 'error',
                'error': str(e),
                'runtime': time.time() - start_time,
                'log_files': {
                    'stdout': str(stdout_log) if 'stdout_log' in locals() else None,
                    'stderr': str(stderr_log) if 'stderr_log' in locals() else None,
                    'combined': str(combined_log) if 'combined_log' in locals() else None
                }
            }
            return "", layout_info
    
    def _extract_hpwl_from_output(
        self,
        stdout: str,
        stderr: str
    ) -> float:
        """
        从OpenRoad detailed placement的输出中提取HPWL
        
        注意：只能使用legalized HPWL（detailed placement后的最终HPWL）
        不能使用original HPWL（那是global placement后的值，还未legalized）
        
        实际输出格式示例：
        Placement Analysis
        ---------------------------------
        total displacement          1.4 u
        average displacement        0.7 u
        max displacement            1.0 u
        original HPWL             410.9 u
        legalized HPWL            409.9 u
        delta HPWL                    0 %
        
        Args:
            stdout: 标准输出
            stderr: 标准错误输出
        
        Returns:
            HPWL值（单位：um），只返回legalized HPWL，如果未找到则返回0.0
        """
        import re
        
        # 合并stdout和stderr，查找HPWL信息
        output = stdout + "\n" + stderr
        
        # 只匹配legalized HPWL（这是detailed placement后的最终HPWL）
        # 格式：legalized HPWL            409.9 u
        legalized_pattern = r'legalized\s+HPWL\s+([\d.]+)\s*u'
        match = re.search(legalized_pattern, output, re.IGNORECASE)
        if match:
            try:
                hpwl_value = float(match.group(1))
                return hpwl_value
            except ValueError:
                pass
        
        # 如果未找到legalized HPWL，返回0.0（后续会从DEF文件计算）
        # 注意：不使用original HPWL，因为那是global placement后的值，还未legalized
        return 0.0
    
    def calculate_hpwl(
        self,
        layout_def_file: str
    ) -> float:
        """
        从OpenRoad布局结果中提取HPWL
        
        Args:
            layout_def_file: 布局DEF文件路径
        
        Returns:
            HPWL值（单位：um）
        
        注意：
        - 使用DEF文件解析方法计算HPWL（不依赖已废弃的report_wirelength命令）
        - HPWL类型取决于DEF文件的来源：
          * 如果DEF文件是detailed placement后的输出，则计算的是legalized HPWL
          * 如果DEF文件是global placement后的输出，则计算的是original HPWL
          * 如果DEF文件是初始floorplan（组件未放置），则计算的是基于初始位置的HPWL
        """
        if not Path(layout_def_file).exists():
            raise FileNotFoundError(f"布局DEF文件不存在: {layout_def_file}")
        
        # 使用DEF解析器计算HPWL
        parser = DEFParser(layout_def_file)
        parser.parse()
        total_hpwl = parser.calculate_total_hpwl()
        
        return total_hpwl
    
    def calculate_partition_hpwl(
        self,
        layout_def_file: str,
        partition_scheme: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        计算各分区内部HPWL（排除跨分区连接）
        
        Args:
            layout_def_file: 布局DEF文件路径
            partition_scheme: 分区方案
        
        Returns:
            各分区内部HPWL字典 {partition_id: hpwl}
        """
        if not Path(layout_def_file).exists():
            raise FileNotFoundError(f"布局DEF文件不存在: {layout_def_file}")
        
        # 解析DEF文件
        parser = DEFParser(layout_def_file)
        parser.parse()
        
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        # 计算各分区内部HPWL
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
        
        return partition_hpwls
    
    def extract_boundary_connections(
        self,
        layout_def_file: str,
        partition_scheme: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        提取跨分区连接
        
        Args:
            layout_def_file: 布局DEF文件路径
            partition_scheme: 分区方案
        
        Returns:
            跨分区连接列表，每个连接包含：
                - net_id: net ID
                - modules: 涉及的模块列表
                - partitions: 涉及的分区列表
                - hpwl: net的HPWL
        """
        if not Path(layout_def_file).exists():
            raise FileNotFoundError(f"布局DEF文件不存在: {layout_def_file}")
        
        # 解析DEF文件
        parser = DEFParser(layout_def_file)
        parser.parse()
        
        # 构建模块到分区的映射
        module_to_partition = {}
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                module_to_partition[module_id] = partition_id
        
        boundary_connections = []
        
        for net_name, net_info in parser.nets.items():
            # 检查是否为跨分区net
            connections = net_info['connections']
            partitions_involved = set()
            modules_involved = set()
            
            for conn in connections:
                comp_name = conn['component']
                modules_involved.add(comp_name)
                
                # 查找组件所属分区
                for module_id, partition_id in module_to_partition.items():
                    if module_id in comp_name or comp_name in module_id:
                        partitions_involved.add(partition_id)
                        break
            
            # 如果是跨分区net，添加到结果
            if len(partitions_involved) > 1:
                net_hpwl = parser.calculate_net_hpwl(net_name)
                boundary_connections.append({
                    'net_id': net_name,
                    'modules': list(modules_involved),
                    'partitions': list(partitions_involved),
                    'hpwl': net_hpwl
                })
        
        return boundary_connections
    
    def calculate_boundary_cost(
        self,
        layout_def_file: str,
        partition_scheme: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        计算边界代价
        
        Args:
            layout_def_file: 布局DEF文件路径
            partition_scheme: 分区方案
        
        Returns:
            边界代价相关指标：
                - boundary_cost: 边界代价百分比
                - total_hpwl: 总HPWL
                - partition_hpwls: 各分区内部HPWL
                - boundary_hpwl: 边界HPWL
        """
        # 计算总HPWL
        total_hpwl = self.calculate_hpwl(layout_def_file)
        
        # 计算各分区内部HPWL
        partition_hpwls = self.calculate_partition_hpwl(layout_def_file, partition_scheme)
        
        # 计算分区HPWL之和
        partition_hpwl_sum = sum(partition_hpwls.values())
        
        # 计算边界代价
        if partition_hpwl_sum > 0:
            boundary_cost = ((total_hpwl - partition_hpwl_sum) / partition_hpwl_sum) * 100.0
        else:
            boundary_cost = 0.0
        
        return {
            'boundary_cost': boundary_cost,
            'total_hpwl': total_hpwl,
            'partition_hpwls': partition_hpwls,
            'boundary_hpwl': total_hpwl - partition_hpwl_sum
        }
    
    def save_partition_netlists(
        self,
        partition_scheme: Dict[str, List[str]],
        design_dir: str,
        output_dir: str,
        timestamp: str
    ) -> Dict[str, str]:
        """
        保存每个partition的netlist（Verilog文件）
        
        根据partition_scheme提取每个partition的模块，生成独立的Verilog文件。
        确保与floorplan_with_partition.def中的分区信息一致。
        保存在与log、layout.def相同的目录下，使用时间戳区分版本。
        
        Args:
            partition_scheme: 分区方案 {partition_id: [module_ids]}
            design_dir: 设计目录路径（包含design.v）
            output_dir: 输出目录（与log、layout.def同一目录）
            timestamp: 时间戳（用于区分版本）
        
        Returns:
            字典：{partition_id: netlist_file_path}
        """
        design_path = Path(design_dir)
        verilog_file = design_path / "design.v"
        output_dir = Path(output_dir)
        
        if not verilog_file.exists():
            # 如果没有Verilog文件，返回空字典
            return {}
        
        # 读取原始Verilog文件
        with open(verilog_file, 'r') as f:
            verilog_content = f.read()
        
        # 解析Verilog文件，提取模块定义
        modules = self._parse_verilog_modules(verilog_content)
        
        # 为每个partition生成netlist
        partition_netlists = {}
        for partition_id, module_ids in partition_scheme.items():
            # 提取属于该partition的模块
            partition_modules = {}
            for module_id in module_ids:
                # 查找匹配的模块（支持部分匹配，因为module_id可能是模块名的前缀）
                for module_name, module_def in modules.items():
                    if module_id in module_name or module_name.startswith(module_id):
                        partition_modules[module_name] = module_def
            
            # 生成partition的netlist文件（保存在与log、layout.def同一目录）
            netlist_file = output_dir / f"{partition_id}_{timestamp}.v"
            self._write_partition_netlist(
                partition_modules=partition_modules,
                partition_id=partition_id,
                output_file=netlist_file,
                original_verilog=verilog_content
            )
            
            partition_netlists[partition_id] = str(netlist_file)
        
        # 保存partition方案JSON（用于回溯，与log、layout.def同一目录）
        partition_scheme_file = output_dir / f"partition_scheme_{timestamp}.json"
        
        # 验证一致性：确保partition netlist与floorplan_with_partition.def中的分区信息一致
        consistency_report = self._verify_partition_consistency(
            partition_scheme=partition_scheme,
            design_dir=design_dir,
            partition_netlists=partition_netlists,
            modules=modules
        )
        
        with open(partition_scheme_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'partition_scheme': partition_scheme,
                'netlist_files': partition_netlists,
                'consistency_report': consistency_report
            }, f, indent=2, ensure_ascii=False)
        
        return partition_netlists
    
    def _parse_verilog_modules(self, verilog_content: str) -> Dict[str, str]:
        """
        解析Verilog文件，提取模块定义
        
        Args:
            verilog_content: Verilog文件内容
        
        Returns:
            字典：{module_name: module_definition}
        """
        modules = {}
        lines = verilog_content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 查找module定义
            if line.startswith('module '):
                # 提取模块名
                parts = line.split()
                if len(parts) >= 2:
                    module_name = parts[1].split('(')[0].strip()  # 移除参数列表
                    
                    # 提取整个模块定义（从module到endmodule）
                    module_start = i
                    module_end = i
                    brace_count = 0
                    in_module = False
                    
                    for j in range(i, len(lines)):
                        line_j = lines[j]
                        if 'module ' in line_j and not in_module:
                            in_module = True
                            # 计算开括号数
                            brace_count += line_j.count('(') - line_j.count(')')
                        elif in_module:
                            brace_count += line_j.count('(') - line_j.count(')')
                            if 'endmodule' in line_j and brace_count == 0:
                                module_end = j
                                break
                    
                    # 提取模块内容
                    if module_end > module_start:
                        module_def = '\n'.join(lines[module_start:module_end+1])
                        modules[module_name] = module_def
                        i = module_end + 1
                        continue
            
            i += 1
        
        return modules
    
    def _write_partition_netlist(
        self,
        partition_modules: Dict[str, str],
        partition_id: str,
        output_file: Path,
        original_verilog: str
    ):
        """
        写入partition的netlist文件
        
        Args:
            partition_modules: 该partition包含的模块定义 {module_name: module_definition}
            partition_id: 分区ID
            output_file: 输出文件路径
            original_verilog: 原始Verilog文件内容（用于提取依赖）
        """
        with open(output_file, 'w') as f:
            # 写入文件头
            f.write(f"// Partition Netlist: {partition_id}\n")
            f.write(f"// Generated from partition scheme\n")
            f.write(f"// Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"// This netlist corresponds to the partition defined in floorplan_with_partition.def\n\n")
            
            # 写入该partition的所有模块
            for module_name, module_def in partition_modules.items():
                f.write(module_def)
                f.write("\n\n")
            
            # 如果没有找到模块，写入注释说明
            if not partition_modules:
                f.write(f"// No modules found for partition {partition_id}\n")
                f.write(f"// This may indicate that the module names in partition_scheme\n")
                f.write(f"// do not match the module names in the original Verilog file.\n")
    
    def _verify_partition_consistency(
        self,
        partition_scheme: Dict[str, List[str]],
        design_dir: str,
        partition_netlists: Dict[str, str],
        modules: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        验证partition netlist与floorplan_with_partition.def中的分区信息一致性
        
        验证方法：
        1. 读取floorplan_with_partition.def中的GROUPS部分，获取每个分区的组件列表
        2. 从partition_scheme和modules构建模块到组件的映射
        3. 验证：每个partition的netlist中的模块，对应的组件确实在DEF中该partition的GROUPS中
        
        Args:
            partition_scheme: 分区方案 {partition_id: [module_ids]}
            design_dir: 设计目录路径
            partition_netlists: partition netlist文件路径字典
            modules: 解析的Verilog模块字典
        
        Returns:
            一致性验证报告
        """
        design_path = Path(design_dir)
        def_with_partition = design_path / "floorplan_with_partition.def"
        
        if not def_with_partition.exists():
            return {
                'status': 'warning',
                'message': 'floorplan_with_partition.def not found, cannot verify consistency',
                'verified': False
            }
        
        # 1. 解析DEF文件，提取GROUPS部分
        parser = DEFParser(str(def_with_partition))
        parser.parse()
        
        # 2. 从DEF文件中提取GROUPS信息（如果DEFParser支持）
        # 否则，直接解析DEF文件文本
        def_groups = {}
        try:
            with open(def_with_partition, 'r') as f:
                def_content = f.read()
            
            # 查找GROUPS部分
            import re
            groups_match = re.search(r'GROUPS\s+(\d+)\s+;', def_content)
            if groups_match:
                groups_start = def_content.find('GROUPS')
                groups_end = def_content.find('END GROUPS', groups_start)
                if groups_end == -1:
                    groups_end = len(def_content)
                
                groups_section = def_content[groups_start:groups_end]
                
                # 解析每个GROUP：- group_name comp1 comp2 ... + REGION region_name ;
                group_pattern = r'-\s+(\w+)\s+([^+]+?)\s+\+\s+REGION\s+(\w+)\s+;'
                for match in re.finditer(group_pattern, groups_section, re.MULTILINE | re.DOTALL):
                    group_name = match.group(1)
                    components_str = match.group(2)
                    region_name = match.group(3)
                    
                    # 提取组件名（去除换行和多余空格）
                    components = [c.strip() for c in components_str.split() if c.strip()]
                    def_groups[group_name] = {
                        'region': region_name,
                        'components': components
                    }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to parse GROUPS from DEF file: {e}',
                'verified': False
            }
        
        # 3. 构建模块到组件的映射（与convert_partition_to_def_constraints中的逻辑一致）
        module_to_components = {}
        component_to_partition = {}
        
        # 从DEF文件中获取所有组件名
        all_components = set(parser.components.keys())
        
        for partition_id, module_ids in partition_scheme.items():
            for module_id in module_ids:
                # 查找属于该模块的组件（与convert_partition_to_def_constraints中的逻辑一致）
                components = []
                for comp_name in all_components:
                    if module_id in comp_name or comp_name.startswith(module_id):
                        components.append(comp_name)
                        component_to_partition[comp_name] = partition_id
                
                if module_id not in module_to_components:
                    module_to_components[module_id] = []
                module_to_components[module_id].extend(components)
        
        # 4. 验证一致性
        verification_results = {}
        all_consistent = True
        
        for partition_id, module_ids in partition_scheme.items():
            # 从partition_id提取数字索引（如"partition_0" -> 0）
            import re
            match = re.search(r'(\d+)$', str(partition_id))
            if match:
                partition_index = int(match.group(1))
            else:
                partition_index = 0
            
            group_name = f"er{partition_index}"
            
            # 获取DEF中该分区的组件列表
            def_components = set()
            if group_name in def_groups:
                def_components = set(def_groups[group_name]['components'])
            
            # 获取该partition的netlist中的模块对应的组件
            netlist_components = set()
            for module_id in module_ids:
                if module_id in module_to_components:
                    netlist_components.update(module_to_components[module_id])
            
            # 验证：netlist中的组件应该在DEF的GROUPS中
            missing_in_def = netlist_components - def_components
            extra_in_def = def_components - netlist_components
            
            is_consistent = len(missing_in_def) == 0
            
            verification_results[partition_id] = {
                'group_name': group_name,
                'netlist_modules': module_ids,
                'netlist_components_count': len(netlist_components),
                'def_components_count': len(def_components),
                'missing_in_def': list(missing_in_def),
                'extra_in_def': list(extra_in_def),
                'consistent': is_consistent
            }
            
            if not is_consistent:
                all_consistent = False
        
        return {
            'status': 'success' if all_consistent else 'warning',
            'verified': all_consistent,
            'message': 'All partitions are consistent' if all_consistent else 'Some partitions have inconsistencies',
            'verification_results': verification_results,
            'summary': {
                'total_partitions': len(partition_scheme),
                'consistent_partitions': sum(1 for r in verification_results.values() if r['consistent']),
                'inconsistent_partitions': sum(1 for r in verification_results.values() if not r['consistent'])
            }
        }

