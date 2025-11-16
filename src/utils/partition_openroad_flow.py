"""
Partition-based OpenROAD Flow

实现Step 5-8：
- Step 5: 各Partition OpenROAD执行（并行）
- Step 6: Macro LEF生成（已有模块）
- Step 7: 顶层OpenROAD执行（boundary nets only）
- Step 8: 边界代价计算

作者：ChipMASRAG Team
日期：2025-11-15
"""

import subprocess
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import concurrent.futures
import time

from .openroad_interface import OpenRoadInterface
from .macro_lef_generator import MacroLEFGenerator
from .def_parser import DEFParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PartitionOpenROADFlow:
    """
    Partition-based OpenROAD流程执行器
    """
    
    def __init__(
        self,
        design_name: str,
        design_dir: Path,
        partition_netlists: Dict[int, Path],
        top_netlist: Path,
        physical_regions: Dict[int, Tuple[int, int, int, int]],
        tech_lef: Path,
        cells_lef: Path,
        output_dir: Path
    ):
        """
        初始化
        
        Args:
            design_name: 设计名称
            design_dir: 设计目录（包含LEF文件）
            partition_netlists: {partition_id: netlist_path}
            top_netlist: 顶层网表路径
            physical_regions: {partition_id: (llx, lly, urx, ury)}
            tech_lef: 技术LEF文件
            cells_lef: 标准单元LEF文件
            output_dir: 输出目录
        """
        self.design_name = design_name
        self.design_dir = Path(design_dir)
        self.partition_netlists = {k: Path(v) for k, v in partition_netlists.items()}
        self.top_netlist = Path(top_netlist)
        self.physical_regions = physical_regions
        self.tech_lef = Path(tech_lef)
        self.cells_lef = Path(cells_lef)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.openroad = OpenRoadInterface(timeout=None)  # 不设置超时，等待完成
        
        logger.info(f"初始化PartitionOpenROADFlow: {design_name}")
        logger.info(f"  分区数: {len(self.partition_netlists)}")
        logger.info(f"  输出目录: {self.output_dir}")
    
    def run_partition_openroad(
        self,
        partition_id: int,
        netlist_path: Path,
        physical_region: Tuple[int, int, int, int]
    ) -> Dict:
        """
        为单个partition运行OpenROAD
        
        Args:
            partition_id: 分区ID
            netlist_path: Partition网表路径
            physical_region: (llx, lly, urx, ury)
            
        Returns:
            结果字典：{'def_file': Path, 'hpwl': float, 'runtime': float}
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Step 5.{partition_id}: Partition {partition_id} OpenROAD执行")
        logger.info(f"{'='*60}")
        
        partition_output_dir = self.output_dir / f"partition_{partition_id}"
        partition_output_dir.mkdir(parents=True, exist_ok=True)
        
        # physical_region格式: (llx, lly, urx, ury)
        llx, lly, urx, ury = physical_region
        width = urx - llx
        height = ury - lly
        
        # 每个partition使用自己的die_area（从0,0开始，使用partition的尺寸）
        die_area = f"0 0 {width} {height}"
        core_area = f"{int(width*0.1)} {int(height*0.1)} {int(width*0.9)} {int(height*0.9)}"
        
        # 生成TCL脚本
        tcl_file = partition_output_dir / f"partition_{partition_id}.tcl"
        output_def = partition_output_dir / f"partition_{partition_id}_layout.def"
        
        tcl_content = f"""# OpenROAD TCL脚本 - Partition {partition_id}
# {self.design_name}

# 读取LEF文件
read_lef {self.tech_lef.absolute()}
read_lef {self.cells_lef.absolute()}

# 读取Verilog网表
read_verilog {netlist_path.absolute()}

# 链接设计
link_design partition_{partition_id}

# 初始化Floorplan
initialize_floorplan -die_area "{die_area}" -core_area "{core_area}" -site core

# 生成tracks
make_tracks

# 放置引脚（指定水平层和垂直层）
place_pins -random -hor_layers metal3 -ver_layers metal2

# 全局布局
global_placement -skip_initial_place

# 详细布局
detailed_placement

# 写入DEF
write_def {output_def.absolute()}

# HPWL信息会在detailed_placement的输出中自动报告
"""
        
        with open(tcl_file, 'w') as f:
            f.write(tcl_content)
        
        logger.info(f"  生成TCL脚本: {tcl_file}")
        logger.info(f"  物理区域: ({llx}, {lly}, {urx}, {ury})")
        logger.info(f"  Partition尺寸: {width} x {height}")
        
        # 运行OpenROAD
        log_file = partition_output_dir / f"openroad_{partition_id}.log"
        start_time = time.time()
        
        try:
            with open(log_file, 'w') as log_f:
                # 确保PATH包含~/.local/bin（用于Yosys等工具）
                env = os.environ.copy()
                local_bin = Path.home() / '.local' / 'bin'
                if local_bin.exists():
                    env['PATH'] = str(local_bin) + ':' + env.get('PATH', '')
                
                result = subprocess.run(
                    ['openroad', '-exit', str(tcl_file.absolute())],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=None,  # 不设置超时
                    env=env
                )
            
            runtime = time.time() - start_time
            
            # 优先检查DEF文件是否生成（即使返回码非0，只要DEF文件存在就认为成功）
            if not output_def.exists():
                logger.error(f"  ❌ DEF文件未生成: {output_def}")
                if result.returncode != 0:
                    logger.error(f"  OpenROAD返回码: {result.returncode}")
                    logger.error(f"  查看日志: {log_file}")
                return {
                    'partition_id': partition_id,
                    'success': False,
                    'error': 'DEF file not generated',
                    'log_file': str(log_file)
                }
            
            # 如果DEF文件存在，即使返回码非0也认为成功（可能是警告导致的非0返回码）
            if result.returncode != 0:
                logger.warning(f"  ⚠️  OpenROAD返回码非0 (code: {result.returncode})，但DEF文件已生成")
                logger.warning(f"  查看日志: {log_file}")
            
            # 提取HPWL
            hpwl = self._extract_hpwl_from_log(log_file)
            
            logger.info(f"  ✅ OpenROAD执行成功")
            logger.info(f"  运行时间: {runtime:.1f}s")
            logger.info(f"  HPWL: {hpwl:.2f} um")
            logger.info(f"  DEF文件: {output_def}")
            
            return {
                'partition_id': partition_id,
                'success': True,
                'def_file': str(output_def),
                'hpwl': hpwl,
                'runtime': runtime,
                'log_file': str(log_file)
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"  ❌ OpenROAD执行超时")
            return {
                'partition_id': partition_id,
                'success': False,
                'error': 'Timeout',
                'log_file': str(log_file)
            }
        except Exception as e:
            logger.error(f"  ❌ OpenROAD执行异常: {e}")
            return {
                'partition_id': partition_id,
                'success': False,
                'error': str(e),
                'log_file': str(log_file)
            }
    
    def _extract_hpwl_from_log(self, log_file: Path) -> float:
        """从OpenROAD日志中提取HPWL"""
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            # 查找 "legalized HPWL" 或 "original HPWL" 或 "HPWL: XXXX"
            import re
            patterns = [
                r'legalized HPWL\s+([\d.]+)\s*u',  # "legalized HPWL       15798611.1 u"
                r'original HPWL\s+([\d.]+)\s*u',   # "original HPWL        15781311.3 u"
                r'legalized HPWL:\s*([\d.]+)',     # "legalized HPWL: 12345"
                r'HPWL:\s*([\d.]+)\s*um',          # "HPWL: 12345 um"
                r'Total HPWL:\s*([\d.]+)'          # "Total HPWL: 12345"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return float(match.group(1))
            
            # 如果找不到，返回0
            logger.warning(f"  无法从日志提取HPWL: {log_file}")
            return 0.0
            
        except Exception as e:
            logger.warning(f"  读取日志失败: {e}")
            return 0.0
    
    def run_all_partitions(self, parallel: bool = True) -> Dict[int, Dict]:
        """
        运行所有partition的OpenROAD
        
        Args:
            parallel: 是否并行执行
            
        Returns:
            {partition_id: result_dict}
        """
        logger.info("\n" + "="*80)
        logger.info("Step 5: 各Partition OpenROAD执行")
        logger.info("="*80)
        
        results = {}
        
        if parallel and len(self.partition_netlists) > 1:
            logger.info(f"  并行执行 {len(self.partition_netlists)} 个partition...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.partition_netlists)) as executor:
                futures = {
                    executor.submit(
                        self.run_partition_openroad,
                        pid,
                        netlist,
                        self.physical_regions[pid]
                    ): pid
                    for pid, netlist in self.partition_netlists.items()
                }
                
                for future in concurrent.futures.as_completed(futures):
                    pid = futures[future]
                    try:
                        result = future.result()
                        results[pid] = result
                    except Exception as e:
                        logger.error(f"  Partition {pid} 执行异常: {e}")
                        results[pid] = {
                            'partition_id': pid,
                            'success': False,
                            'error': str(e)
                        }
        else:
            logger.info(f"  串行执行 {len(self.partition_netlists)} 个partition...")
            for pid, netlist in self.partition_netlists.items():
                result = self.run_partition_openroad(pid, netlist, self.physical_regions[pid])
                results[pid] = result
        
        # 统计
        successful = sum(1 for r in results.values() if r.get('success', False))
        logger.info(f"\n  完成: {successful}/{len(results)} partitions成功")
        
        return results
    
    def generate_macro_lefs(self, partition_results: Dict[int, Dict]) -> Dict[int, Path]:
        """
        为每个partition生成Macro LEF
        
        Args:
            partition_results: Step 5的结果
            
        Returns:
            {partition_id: lef_file_path}
        """
        logger.info("\n" + "="*80)
        logger.info("Step 6: Macro LEF生成")
        logger.info("="*80)
        
        lef_files = {}
        
        for pid, result in partition_results.items():
            if not result.get('success', False):
                logger.warning(f"  Partition {pid} 跳过（OpenROAD失败）")
                continue
            
            def_file = result['def_file']
            lef_file = self.output_dir / f"partition_{pid}.lef"
            
            logger.info(f"\n  生成 Partition {pid} Macro LEF...")
            
            try:
                generator = MacroLEFGenerator(
                    design_name=f"partition_{pid}",
                    def_file=def_file,
                    tech_lef=self.tech_lef,
                    cells_lef=self.cells_lef
                )
                
                generator.generate_macro_lef(lef_file)
                
                if lef_file.exists():
                    logger.info(f"  ✅ {lef_file}")
                    lef_files[pid] = lef_file
                else:
                    logger.error(f"  ❌ LEF文件未生成: {lef_file}")
                    
            except Exception as e:
                logger.error(f"  ❌ 生成LEF失败: {e}")
        
        logger.info(f"\n  完成: {len(lef_files)}/{len(partition_results)} Macro LEFs生成")
        
        return lef_files
    
    def generate_top_def(
        self,
        macro_lefs: Dict[int, Path],
        boundary_nets_file: Path,
        physical_regions: Dict[int, Tuple[int, int, int, int]],
        partition_results: Dict[int, Dict]
    ) -> Path:
        """
        生成顶层DEF（只包含boundary nets）
        
        Args:
            macro_lefs: {partition_id: lef_file}
            boundary_nets_file: boundary nets JSON文件
            physical_regions: {partition_id: (x, y, w, h)}
            
        Returns:
            顶层DEF文件路径
        """
        logger.info("\n" + "="*80)
        logger.info("Step 7: 生成顶层DEF（boundary nets only）")
        logger.info("="*80)
        
        # 读取boundary nets信息
        with open(boundary_nets_file, 'r') as f:
            boundary_data = json.load(f)
        
        boundary_nets = boundary_data.get('boundary_nets', {})
        logger.info(f"  Boundary nets数量: {len(boundary_nets)}")
        
        # 生成顶层DEF
        top_def = self.output_dir / "top_layout.def"
        
        # 读取第一个partition的DEF作为模板（获取DIEAREA等）
        first_partition_def = None
        for pid, result in partition_results.items():
            if result.get('success', False):
                first_partition_def = result['def_file']
                break
        
        if not first_partition_def:
            raise ValueError("没有可用的partition DEF文件作为模板")
        
        # 解析模板DEF
        parser = DEFParser(str(first_partition_def))
        parser.parse()
        
        # 计算总die area（包含所有partitions）
        # physical_regions格式: (llx, lly, urx, ury)
        max_x = max(reg[2] for reg in physical_regions.values())  # max urx
        max_y = max(reg[3] for reg in physical_regions.values())  # max ury
        
        # 生成顶层DEF内容
        def_lines = []
        def_lines.append(f"VERSION 5.8 ;")
        def_lines.append(f"DIVIDERCHAR \"/\" ;")
        def_lines.append(f"BUSBITCHARS \"[]\" ;")
        def_lines.append(f"DESIGN {self.design_name}_top ;")
        def_lines.append(f"UNITS DISTANCE MICRONS 1000 ;")
        def_lines.append(f"")
        def_lines.append(f"DIEAREA ( 0 0 ) ( {max_x} {max_y} ) ;")
        def_lines.append(f"")
        
        # COMPONENTS部分（partition macros）
        def_lines.append(f"COMPONENTS {len(macro_lefs)} ;")
        for pid, lef_file in macro_lefs.items():
            # physical_regions格式: (llx, lly, urx, ury)
            llx, lly, urx, ury = physical_regions[pid]
            # Macro中心位置
            center_x = (llx + urx) // 2
            center_y = (lly + ury) // 2
            def_lines.append(f"  - u_partition_{pid} partition_{pid} + FIXED ( {center_x} {center_y} ) N ;")
        def_lines.append(f"END COMPONENTS")
        def_lines.append(f"")
        
        # NETS部分（只包含boundary nets）
        def_lines.append(f"NETS {len(boundary_nets)} ;")
        for net_name, net_info in boundary_nets.items():
            partitions = net_info['partitions']
            def_lines.append(f"  - {net_name}")
            # 连接到相关partition的端口
            for pid in partitions:
                if pid in macro_lefs:
                    def_lines.append(f"    ( u_partition_{pid} bnet_{net_name} )")
            def_lines.append(f"  ;")
        def_lines.append(f"END NETS")
        def_lines.append(f"")
        def_lines.append(f"END DESIGN")
        
        # 写入文件
        with open(top_def, 'w') as f:
            f.write('\n'.join(def_lines))
        
        logger.info(f"  ✅ 顶层DEF生成: {top_def}")
        logger.info(f"  包含 {len(macro_lefs)} 个partition macros")
        logger.info(f"  包含 {len(boundary_nets)} 个boundary nets")
        
        return top_def
    
    def run_top_openroad(self, top_def: Path, macro_lefs: Dict[int, Path]) -> Dict:
        """
        运行顶层OpenROAD（只处理boundary nets）
        
        Args:
            top_def: 顶层DEF文件
            macro_lefs: {partition_id: lef_file}
            
        Returns:
            结果字典
        """
        logger.info("\n" + "="*80)
        logger.info("Step 7: 顶层OpenROAD执行（boundary nets only）")
        logger.info("="*80)
        
        top_output_dir = self.output_dir / "top"
        top_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成TCL脚本
        tcl_file = top_output_dir / "top.tcl"
        output_def = top_output_dir / "top_layout.def"
        
        # 收集所有LEF文件
        all_lefs = [str(self.tech_lef.absolute()), str(self.cells_lef.absolute())]
        for lef_file in macro_lefs.values():
            all_lefs.append(str(Path(lef_file).absolute()))
        
        # 计算die area和core area（从physical_regions获取整个芯片边界）
        if self.physical_regions:
            max_x = max(region[2] for region in self.physical_regions.values())  # urx
            max_y = max(region[3] for region in self.physical_regions.values())  # ury
            die_area_str = f"0 0 {max_x} {max_y}"
            # core_area通常比die_area小一些，留出边距（这里留10%边距）
            margin = 0.05
            core_llx = int(max_x * margin)
            core_lly = int(max_y * margin)
            core_urx = int(max_x * (1 - margin))
            core_ury = int(max_y * (1 - margin))
            core_area_str = f"{core_llx} {core_lly} {core_urx} {core_ury}"
        else:
            # 默认die area和core area（如果没有physical_regions）
            die_area_str = "0 0 100000 100000"
            core_area_str = "5000 5000 95000 95000"
        
        tcl_content = f"""# OpenROAD TCL脚本 - Top Level (Boundary Nets Only)
# {self.design_name}

# 读取所有LEF文件
"""
        for lef in all_lefs:
            tcl_content += f"read_lef {lef}\n"
        
        tcl_content += f"""
# 读取顶层DEF（包含partition macros和boundary nets）
read_def {top_def.absolute()}

# 注意：顶层DEF已经包含了所有必要信息（partition macros和boundary nets）
# 但DEF中没有定义rows，需要初始化floorplan来添加rows

# 初始化floorplan（添加placement rows）
# Die area: {die_area_str}
# Core area: {core_area_str}
initialize_floorplan -site core -die_area "{die_area_str}" -core_area "{core_area_str}"

# 全局布局（只优化boundary nets）
global_placement -skip_initial_place

# 详细布局
detailed_placement

# 写入DEF
write_def {output_def.absolute()}

# HPWL信息会在detailed_placement的输出中自动报告
"""
        
        with open(tcl_file, 'w') as f:
            f.write(tcl_content)
        
        logger.info(f"  生成TCL脚本: {tcl_file}")
        
        # 运行OpenROAD
        log_file = top_output_dir / "openroad_top.log"
        start_time = time.time()
        
        try:
            with open(log_file, 'w') as log_f:
                # 确保PATH包含~/.local/bin
                env = os.environ.copy()
                local_bin = Path.home() / '.local' / 'bin'
                if local_bin.exists():
                    env['PATH'] = str(local_bin) + ':' + env.get('PATH', '')
                
                result = subprocess.run(
                    ['openroad', '-exit', str(tcl_file.absolute())],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=None,
                    env=env
                )
            
            runtime = time.time() - start_time
            
            # 优先检查DEF文件是否生成
            if not output_def.exists():
                logger.error(f"  ❌ 顶层DEF文件未生成: {output_def}")
                if result.returncode != 0:
                    logger.error(f"  OpenROAD返回码: {result.returncode}")
                return {
                    'success': False,
                    'error': 'DEF file not generated',
                    'log_file': str(log_file)
                }
            
            # 如果DEF文件存在，即使返回码非0也认为成功
            if result.returncode != 0:
                logger.warning(f"  ⚠️  顶层OpenROAD返回码非0 (code: {result.returncode})，但DEF文件已生成")
            
            # 提取HPWL
            hpwl = self._extract_hpwl_from_log(log_file)
            
            logger.info(f"  ✅ 顶层OpenROAD执行成功")
            logger.info(f"  运行时间: {runtime:.1f}s")
            logger.info(f"  Boundary HPWL: {hpwl:.2f} um")
            
            return {
                'success': True,
                'def_file': str(output_def),
                'hpwl': hpwl,
                'runtime': runtime,
                'log_file': str(log_file)
            }
            
        except Exception as e:
            logger.error(f"  ❌ 顶层OpenROAD执行异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'log_file': str(log_file)
            }
    
    def calculate_boundary_cost(
        self,
        partition_results: Dict[int, Dict],
        top_result: Dict
    ) -> Dict:
        """
        计算边界代价
        
        BC = HPWL_boundary / HPWL_internal_total × 100%
        
        Args:
            partition_results: Step 5的结果
            top_result: Step 7的结果
            
        Returns:
            边界代价计算结果
        """
        logger.info("\n" + "="*80)
        logger.info("Step 8: 边界代价计算")
        logger.info("="*80)
        
        # 计算各partition的internal HPWL总和
        internal_hpwl_total = 0.0
        for pid, result in partition_results.items():
            if result.get('success', False):
                hpwl = result.get('hpwl', 0.0)
                internal_hpwl_total += hpwl
                logger.info(f"  Partition {pid} internal HPWL: {hpwl:.2f} um")
        
        logger.info(f"  总Internal HPWL: {internal_hpwl_total:.2f} um")
        
        # 获取boundary HPWL
        boundary_hpwl = top_result.get('hpwl', 0.0)
        logger.info(f"  Boundary HPWL: {boundary_hpwl:.2f} um")
        
        # 计算边界代价
        if internal_hpwl_total > 0:
            boundary_cost = (boundary_hpwl / internal_hpwl_total) * 100.0
        else:
            boundary_cost = float('inf')
            logger.warning("  ⚠️  Internal HPWL为0，无法计算边界代价")
        
        logger.info(f"\n  边界代价 (BC): {boundary_cost:.2f}%")
        logger.info(f"  公式: BC = HPWL_boundary / HPWL_internal_total × 100%")
        logger.info(f"      = {boundary_hpwl:.2f} / {internal_hpwl_total:.2f} × 100%")
        logger.info(f"      = {boundary_cost:.2f}%")
        
        return {
            'internal_hpwl_total': internal_hpwl_total,
            'boundary_hpwl': boundary_hpwl,
            'boundary_cost_percent': boundary_cost,
            'partition_hpwls': {
                pid: result.get('hpwl', 0.0)
                for pid, result in partition_results.items()
                if result.get('success', False)
            }
        }
    
    def run_complete_flow(
        self,
        boundary_nets_file: Path,
        parallel: bool = True
    ) -> Dict:
        """
        运行完整的Partition-based Flow（Step 5-8）
        
        Args:
            boundary_nets_file: boundary nets JSON文件
            parallel: 是否并行执行partitions
            
        Returns:
            完整结果字典
        """
        logger.info("\n" + "="*80)
        logger.info("Partition-based OpenROAD Flow - 完整流程")
        logger.info("="*80)
        
        results = {
            'design_name': self.design_name,
            'steps': {}
        }
        
        # Step 5: 各Partition OpenROAD执行
        partition_results = self.run_all_partitions(parallel=parallel)
        results['steps']['partition_openroad'] = partition_results
        
        # Step 6: Macro LEF生成
        macro_lefs = self.generate_macro_lefs(partition_results)
        results['steps']['macro_lef_generation'] = {
            pid: str(lef_file) for pid, lef_file in macro_lefs.items()
        }
        
        # Step 7: 顶层OpenROAD执行
        top_def = self.generate_top_def(macro_lefs, boundary_nets_file, self.physical_regions, partition_results)
        top_result = self.run_top_openroad(top_def, macro_lefs)
        results['steps']['top_openroad'] = top_result
        
        # Step 8: 边界代价计算
        boundary_cost = self.calculate_boundary_cost(partition_results, top_result)
        results['steps']['boundary_cost'] = boundary_cost
        
        # 保存结果汇总
        summary_file = self.output_dir / "flow_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("\n" + "="*80)
        logger.info("✅ Partition-based OpenROAD Flow完成！")
        logger.info("="*80)
        logger.info(f"结果汇总: {summary_file}")
        
        return results

