"""
从cells.lef提取标准单元信息并生成Verilog黑盒定义

用于Formal验证时提供标准单元定义
"""

import re
from pathlib import Path
from typing import Dict, List, Set


def parse_lef_cell(lef_content: str, cell_name: str) -> Dict:
    """
    从LEF内容中解析单个标准单元的信息
    
    Returns:
        {
            'name': cell_name,
            'pins': {
                'pin_name': {'direction': 'INPUT'/'OUTPUT'/'INOUT'}
            }
        }
    """
    # 查找MACRO定义
    macro_pattern = rf'MACRO\s+{cell_name}\s+(.*?)(?=MACRO|END\s+MACRO|$)'
    match = re.search(macro_pattern, lef_content, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return None
    
    macro_content = match.group(1)
    
    # 解析PIN定义
    pins = {}
    pin_pattern = r'PIN\s+(\w+)\s+(.*?)(?=END\s+\1|PIN|$)'
    
    for pin_match in re.finditer(pin_pattern, macro_content, re.DOTALL | re.IGNORECASE):
        pin_name = pin_match.group(1)
        pin_content = pin_match.group(2)
        
        # 查找DIRECTION
        direction_match = re.search(r'DIRECTION\s+(\w+)', pin_content, re.IGNORECASE)
        if direction_match:
            direction = direction_match.group(1).upper()
            pins[pin_name] = {'direction': direction}
    
    return {
        'name': cell_name,
        'pins': pins
    }


def generate_verilog_blackbox(cell_info: Dict) -> str:
    """
    生成标准单元的Verilog黑盒定义
    """
    if not cell_info or not cell_info.get('pins'):
        return None
    
    cell_name = cell_info['name']
    pins = cell_info['pins']
    
    # 分离输入和输出
    inputs = []
    outputs = []
    inouts = []
    
    for pin_name, pin_data in pins.items():
        direction = pin_data.get('direction', 'INPUT')
        if direction == 'INPUT':
            inputs.append(pin_name)
        elif direction == 'OUTPUT':
            outputs.append(pin_name)
        elif direction == 'INOUT':
            inouts.append(pin_name)
    
    # 生成Verilog代码
    lines = [f"module {cell_name}("]
    
    # 端口列表
    port_list = []
    for inp in inputs:
        port_list.append(f"input {inp}")
    for out in outputs:
        port_list.append(f"output {out}")
    for inout in inouts:
        port_list.append(f"inout {inout}")
    
    if port_list:
        for i, port in enumerate(port_list):
            if i == len(port_list) - 1:
                lines.append(f"  {port}")
            else:
                lines.append(f"  {port},")
    
    lines.append(");")
    lines.append("  // Black box - no internal logic")
    lines.append("endmodule")
    lines.append("")
    
    return '\n'.join(lines)


def extract_cells_from_verilog(verilog_file: Path) -> Set[str]:
    """
    从Verilog网表中提取使用的标准单元类型
    """
    with open(verilog_file, 'r') as f:
        content = f.read()
    
    # 查找标准单元实例化
    # 格式: cell_type instance_name (...)
    pattern = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', re.MULTILINE)
    
    cell_types = set()
    for match in pattern.finditer(content):
        cell_type = match.group(1)
        # 排除关键字和模块名
        if cell_type not in ['module', 'wire', 'input', 'output', 'reg', 'assign', 'always', 'if', 'else', 'endmodule']:
            cell_types.add(cell_type)
    
    return cell_types


def generate_stdcell_verilog(
    cells_lef: Path,
    verilog_files: List[Path],
    output_file: Path
):
    """
    从cells.lef和Verilog网表中生成标准单元的Verilog黑盒定义
    
    Args:
        cells_lef: cells.lef文件路径
        verilog_files: Verilog网表文件列表（用于提取使用的标准单元）
        output_file: 输出的Verilog定义文件路径
    """
    # 读取LEF文件
    with open(cells_lef, 'r') as f:
        lef_content = f.read()
    
    # 从Verilog文件中提取使用的标准单元类型
    used_cells = set()
    for vfile in verilog_files:
        if vfile.exists():
            used_cells.update(extract_cells_from_verilog(vfile))
    
    print(f"找到 {len(used_cells)} 种标准单元类型")
    
    # 生成Verilog定义
    verilog_defs = []
    verilog_defs.append("// Standard cell black box definitions")
    verilog_defs.append("// Generated from cells.lef")
    verilog_defs.append("")
    
    found_cells = 0
    missing_cells = []
    
    for cell_name in sorted(used_cells):
        cell_info = parse_lef_cell(lef_content, cell_name)
        if cell_info:
            verilog_code = generate_verilog_blackbox(cell_info)
            if verilog_code:
                verilog_defs.append(verilog_code)
                found_cells += 1
        else:
            missing_cells.append(cell_name)
    
    # 写入文件
    with open(output_file, 'w') as f:
        f.write('\n'.join(verilog_defs))
    
    print(f"生成 {found_cells} 个标准单元定义")
    if missing_cells:
        print(f"警告：{len(missing_cells)} 个标准单元在LEF中未找到: {missing_cells[:10]}")
    
    return output_file


if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 3:
        print("Usage: python generate_stdcell_verilog.py <cells.lef> <verilog_file1> [verilog_file2 ...] <output.v>")
        sys.exit(1)
    
    cells_lef = Path(sys.argv[1])
    output_file = Path(sys.argv[-1])
    verilog_files = [Path(f) for f in sys.argv[2:-1]]
    
    generate_stdcell_verilog(cells_lef, verilog_files, output_file)
    print(f"标准单元定义已生成: {output_file}")

