#!/usr/bin/env python3
"""
将 ISPD 2015 DEF 文件转换为 K-SpecPart 可用的超图格式 (.hgr)

K-SpecPart 超图格式说明：
- 第一行：<num_hyperedges> <num_vertices> [fmt]
- 后续每行：一个超边，包含其连接的顶点列表（空格分隔）
- 顶点编号：1-based（第一个顶点是1，不是0）

使用方法：
    python scripts/convert_ispd2015_to_hgr.py \
        --def-file data/ispd2015/mgc_fft_1/floorplan.def \
        --output results/kspecpart/mgc_fft_1.hgr \
        --mapping results/kspecpart/mgc_fft_1.mapping.json
"""

import argparse
import json
from pathlib import Path
import sys

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.def_parser import DEFParser


def convert_ispd2015_to_hgr(def_file, output_hgr, output_mapping=None):
    """
    将 ISPD 2015 DEF 文件转换为 K-SpecPart 可用的超图格式
    
    Args:
        def_file: ISPD 2015 DEF 文件路径
        output_hgr: 输出的 .hgr 文件路径
        output_mapping: （可选）输出顶点映射关系的 JSON 文件路径
    
    Returns:
        vertex_to_id: 字典，component_name -> vertex_id（1-based）
    """
    print(f"正在解析 DEF 文件: {def_file}")
    
    # 1. 解析 DEF 文件
    parser = DEFParser(str(def_file))
    parser.parse()
    
    # 2. 提取超图信息
    components = list(parser.components.keys())
    print(f"  - 找到 {len(components)} 个组件（顶点）")
    
    # 创建映射：component_name -> vertex_id（K-SpecPart 使用 1-based index）
    vertex_to_id = {comp: i+1 for i, comp in enumerate(components)}
    
    # 提取超边（每个 net 是一个超边）
    hyperedges = []
    for net_name, net_info in parser.nets.items():
        # 提取 net 连接的 components
        connected_vertices = []
        for conn in net_info.get('connections', []):
            comp = conn.get('component')  # 修复：使用'component'而不是'comp'
            if comp and comp in vertex_to_id:
                connected_vertices.append(vertex_to_id[comp])
        
        # 只保留连接 2 个及以上顶点的超边
        if len(connected_vertices) >= 2:
            hyperedges.append(sorted(connected_vertices))  # 排序以保持一致性
    
    print(f"  - 找到 {len(hyperedges)} 个超边（网线）")
    
    # 3. 写入 .hgr 文件
    output_hgr = Path(output_hgr)
    output_hgr.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_hgr, 'w') as f:
        # 第一行：<num_hyperedges> <num_vertices>
        f.write(f"{len(hyperedges)} {len(components)}\n")
        
        # 每行一个超边：顶点列表（空格分隔）
        for hedge in hyperedges:
            f.write(" ".join(map(str, hedge)) + "\n")
    
    print(f"✓ 超图文件已保存: {output_hgr}")
    print(f"  格式: {len(hyperedges)} 个超边, {len(components)} 个顶点")
    
    # 4. （可选）保存映射关系
    if output_mapping:
        output_mapping = Path(output_mapping)
        output_mapping.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建反向映射：vertex_id -> component_name
        id_to_vertex = {v_id: v_name for v_name, v_id in vertex_to_id.items()}
        
        mapping_data = {
            'num_vertices': len(components),
            'num_hyperedges': len(hyperedges),
            'vertex_to_id': vertex_to_id,  # component_name -> vertex_id (1-based)
            'id_to_vertex': id_to_vertex   # vertex_id (1-based) -> component_name
        }
        
        with open(output_mapping, 'w') as f:
            json.dump(mapping_data, f, indent=2)
        
        print(f"✓ 映射关系已保存: {output_mapping}")
    
    return vertex_to_id


def main():
    parser = argparse.ArgumentParser(
        description='将 ISPD 2015 DEF 文件转换为 K-SpecPart 超图格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  # 单个设计转换
  python scripts/convert_ispd2015_to_hgr.py \\
      --def-file data/ispd2015/mgc_fft_1/floorplan.def \\
      --output results/kspecpart/mgc_fft_1.hgr \\
      --mapping results/kspecpart/mgc_fft_1.mapping.json
  
  # 批量转换
  for design in mgc_fft_1 mgc_des_perf_1 mgc_matrix_mult_1; do
      python scripts/convert_ispd2015_to_hgr.py \\
          --def-file data/ispd2015/$design/floorplan.def \\
          --output results/kspecpart/$design.hgr \\
          --mapping results/kspecpart/$design.mapping.json
  done
        '''
    )
    
    parser.add_argument(
        '--def-file',
        type=str,
        required=True,
        help='输入的 ISPD 2015 DEF 文件路径'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='输出的 .hgr 文件路径'
    )
    
    parser.add_argument(
        '--mapping',
        type=str,
        help='（可选）输出顶点映射关系的 JSON 文件路径'
    )
    
    args = parser.parse_args()
    
    # 执行转换
    convert_ispd2015_to_hgr(args.def_file, args.output, args.mapping)
    
    print("\n转换完成！")
    print(f"可以使用以下命令运行 K-SpecPart:")
    print(f"  cd ~/chipmas/HypergraphPartitioning/K_SpecPart")
    print(f"  julia run_kspecpart.jl {args.output} 4 0.05 {args.output}.part.4")


if __name__ == '__main__':
    main()


