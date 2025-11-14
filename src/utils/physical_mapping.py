"""
物理位置映射优化模块

基于分区间连接性优化逻辑分区到物理区域的映射
"""

from typing import Dict, Tuple, List
import numpy as np
from pathlib import Path


def analyze_partition_connectivity(
    boundary_connections: Dict
) -> np.ndarray:
    """
    分析分区间连接性
    
    Args:
        boundary_connections: 边界连接信息（来自hierarchical_transformation）
        
    Returns:
        connectivity_matrix: [K x K] 矩阵
        connectivity_matrix[i][j] = 分区i和分区j之间的net数量
    """
    # 1. 确定分区数量
    all_partitions = set()
    for net_info in boundary_connections.values():
        if net_info['is_boundary']:
            all_partitions.update(net_info['partitions'])
    
    if len(all_partitions) == 0:
        return np.zeros((0, 0))
    
    num_partitions = max(all_partitions) + 1
    
    # 2. 构建连接性矩阵
    connectivity_matrix = np.zeros((num_partitions, num_partitions), dtype=int)
    
    for net_info in boundary_connections.values():
        if not net_info['is_boundary']:
            continue
        
        partitions = net_info['partitions']
        
        # 对于每对分区，增加连接计数
        for i in range(len(partitions)):
            for j in range(i + 1, len(partitions)):
                p1, p2 = partitions[i], partitions[j]
                connectivity_matrix[p1][p2] += 1
                connectivity_matrix[p2][p1] += 1  # 对称矩阵
    
    return connectivity_matrix


def optimize_physical_layout(
    num_partitions: int,
    connectivity_matrix: np.ndarray,
    die_area: Tuple[int, int, int, int],
    method: str = 'greedy'
) -> Dict[int, Tuple[int, int, int, int]]:
    """
    优化物理位置映射
    
    Args:
        num_partitions: 分区数量
        connectivity_matrix: 分区间连接性矩阵 [K x K]
        die_area: Die区域 (llx, lly, urx, ury)
        method: 优化方法 ('greedy' 或 'simple')
        
    Returns:
        physical_regions: {
            partition_id: (llx, lly, urx, ury),
            ...
        }
    """
    if method == 'simple':
        return _simple_grid_layout(num_partitions, die_area)
    elif method == 'greedy':
        return _greedy_optimization(
            num_partitions,
            connectivity_matrix,
            die_area
        )
    else:
        raise ValueError(f"Unknown method: {method}")


def _simple_grid_layout(
    num_partitions: int,
    die_area: Tuple[int, int, int, int]
) -> Dict[int, Tuple[int, int, int, int]]:
    """
    简单的网格布局（不考虑连接性）
    
    对于K=4: 2x2网格
    对于K=9: 3x3网格
    """
    llx, lly, urx, ury = die_area
    width = urx - llx
    height = ury - lly
    
    # 确定网格大小
    if num_partitions == 4:
        grid_rows, grid_cols = 2, 2
    elif num_partitions == 9:
        grid_rows, grid_cols = 3, 3
    elif num_partitions == 16:
        grid_rows, grid_cols = 4, 4
    else:
        # 默认：尽可能接近正方形
        grid_cols = int(np.ceil(np.sqrt(num_partitions)))
        grid_rows = int(np.ceil(num_partitions / grid_cols))
    
    # 计算每个分区的尺寸
    partition_width = width // grid_cols
    partition_height = height // grid_rows
    
    # 生成物理区域
    physical_regions = {}
    
    for pid in range(num_partitions):
        row = pid // grid_cols
        col = pid % grid_cols
        
        p_llx = llx + col * partition_width
        p_lly = lly + row * partition_height
        p_urx = p_llx + partition_width
        p_ury = p_lly + partition_height
        
        # 最后一行/列扩展到边界
        if col == grid_cols - 1:
            p_urx = urx
        if row == grid_rows - 1:
            p_ury = ury
        
        physical_regions[pid] = (p_llx, p_lly, p_urx, p_ury)
    
    return physical_regions


def _greedy_optimization(
    num_partitions: int,
    connectivity_matrix: np.ndarray,
    die_area: Tuple[int, int, int, int]
) -> Dict[int, Tuple[int, int, int, int]]:
    """
    贪心算法优化物理位置
    
    策略：
    1. 首先将连接性最强的分区对放置在相邻位置
    2. 逐步放置剩余分区，优先与已放置分区连接强的
    """
    llx, lly, urx, ury = die_area
    width = urx - llx
    height = ury - lly
    
    # 确定网格大小
    if num_partitions == 4:
        grid_rows, grid_cols = 2, 2
    elif num_partitions == 9:
        grid_rows, grid_cols = 3, 3
    else:
        grid_cols = int(np.ceil(np.sqrt(num_partitions)))
        grid_rows = int(np.ceil(num_partitions / grid_cols))
    
    partition_width = width // grid_cols
    partition_height = height // grid_rows
    
    # 物理网格位置
    grid_positions = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            if len(grid_positions) < num_partitions:
                p_llx = llx + col * partition_width
                p_lly = lly + row * partition_height
                p_urx = p_llx + partition_width if col < grid_cols - 1 else urx
                p_ury = p_lly + partition_height if row < grid_rows - 1 else ury
                
                grid_positions.append({
                    'row': row,
                    'col': col,
                    'region': (p_llx, p_lly, p_urx, p_ury)
                })
    
    # 贪心分配
    # 1. 找到连接性最强的分区对
    max_conn = 0
    start_pair = (0, 1)
    
    for i in range(num_partitions):
        for j in range(i + 1, num_partitions):
            if connectivity_matrix[i][j] > max_conn:
                max_conn = connectivity_matrix[i][j]
                start_pair = (i, j)
    
    # 2. 将起始分区对放置在相邻位置（左下和右下）
    partition_to_grid = {}
    grid_to_partition = {}
    
    partition_to_grid[start_pair[0]] = 0  # 左下
    grid_to_partition[0] = start_pair[0]
    
    # 找到与grid 0相邻的位置
    adjacent_to_0 = _get_adjacent_grids(0, grid_rows, grid_cols)
    if len(adjacent_to_0) > 0:
        partition_to_grid[start_pair[1]] = adjacent_to_0[0]
        grid_to_partition[adjacent_to_0[0]] = start_pair[1]
    else:
        partition_to_grid[start_pair[1]] = 1
        grid_to_partition[1] = start_pair[1]
    
    # 3. 逐步放置剩余分区
    placed_partitions = set(start_pair)
    
    while len(placed_partitions) < num_partitions:
        # 找到未放置的分区中，与已放置分区连接最强的
        best_partition = None
        best_score = -1
        
        for pid in range(num_partitions):
            if pid in placed_partitions:
                continue
            
            # 计算与已放置分区的总连接数
            score = sum(
                connectivity_matrix[pid][placed_pid]
                for placed_pid in placed_partitions
            )
            
            if score > best_score:
                best_score = score
                best_partition = pid
        
        if best_partition is None:
            # 随机选择一个
            for pid in range(num_partitions):
                if pid not in placed_partitions:
                    best_partition = pid
                    break
        
        # 找到最佳放置位置（与已放置分区最接近）
        best_grid = None
        best_grid_score = -1
        
        for grid_id in range(len(grid_positions)):
            if grid_id in grid_to_partition:
                continue
            
            # 计算该grid与已放置分区的邻接度
            adjacent_grids = _get_adjacent_grids(
                grid_id, grid_rows, grid_cols
            )
            
            score = 0
            for adj_grid in adjacent_grids:
                if adj_grid in grid_to_partition:
                    adj_partition = grid_to_partition[adj_grid]
                    score += connectivity_matrix[best_partition][adj_partition]
            
            if score > best_grid_score or best_grid is None:
                best_grid_score = score
                best_grid = grid_id
        
        if best_grid is None:
            # 找到第一个空位
            for grid_id in range(len(grid_positions)):
                if grid_id not in grid_to_partition:
                    best_grid = grid_id
                    break
        
        # 放置分区
        partition_to_grid[best_partition] = best_grid
        grid_to_partition[best_grid] = best_partition
        placed_partitions.add(best_partition)
    
    # 4. 生成最终的物理区域映射
    physical_regions = {}
    for pid in range(num_partitions):
        grid_id = partition_to_grid[pid]
        physical_regions[pid] = grid_positions[grid_id]['region']
    
    return physical_regions


def _get_adjacent_grids(
    grid_id: int,
    grid_rows: int,
    grid_cols: int
) -> List[int]:
    """获取相邻的grid位置（上下左右）"""
    row = grid_id // grid_cols
    col = grid_id % grid_cols
    
    adjacent = []
    
    # 上
    if row > 0:
        adjacent.append((row - 1) * grid_cols + col)
    # 下
    if row < grid_rows - 1:
        adjacent.append((row + 1) * grid_cols + col)
    # 左
    if col > 0:
        adjacent.append(row * grid_cols + (col - 1))
    # 右
    if col < grid_cols - 1:
        adjacent.append(row * grid_cols + (col + 1))
    
    return adjacent


def visualize_physical_mapping(
    physical_regions: Dict[int, Tuple[int, int, int, int]],
    connectivity_matrix: np.ndarray,
    output_path: Path
):
    """
    可视化物理映射
    
    Args:
        physical_regions: 物理区域映射
        connectivity_matrix: 连接性矩阵
        output_path: 输出图片路径
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError:
        print("警告: matplotlib未安装，跳过可视化")
        return
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # 绘制各分区
    for pid, (llx, lly, urx, ury) in physical_regions.items():
        width = urx - llx
        height = ury - lly
        
        rect = patches.Rectangle(
            (llx, lly), width, height,
            linewidth=2,
            edgecolor='black',
            facecolor='lightblue',
            alpha=0.5
        )
        ax.add_patch(rect)
        
        # 标注分区ID
        cx = (llx + urx) / 2
        cy = (lly + ury) / 2
        ax.text(cx, cy, f'P{pid}', ha='center', va='center', fontsize=14, weight='bold')
    
    # 绘制连接（可选）
    # TODO: 绘制分区间的连接线
    
    ax.set_aspect('equal')
    ax.set_xlim(auto=True)
    ax.set_ylim(auto=True)
    ax.set_title('Physical Partition Mapping', fontsize=16)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✓ 可视化已保存: {output_path}")

