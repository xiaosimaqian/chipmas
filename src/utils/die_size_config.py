"""
Die Size 配置模块
从参考成功案例中提取的 die size 配置
"""

from typing import Tuple, List

# 从 ~/dreamplace_experiment/chipkag/results/chipkag_complete_experiment/ 提取的成功案例 die size
# 格式: {设计名: (die_area, core_area)}
# die_area: "x1 y1 x2 y2"
# core_area: "x1 y1 x2 y2"

DIE_SIZE_CONFIG = {
    # 大部分设计使用 5000x5000
    "mgc_des_perf_1": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_des_perf_a": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_edit_dist_a": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_fft_1": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_fft_2": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_matrix_mult_1": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_matrix_mult_b": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_pci_bridge32_a": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_pci_bridge32_b": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_superblue11_a": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_superblue12": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_superblue14": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_superblue16_a": ("0 0 5000 5000", "250 250 4750 4750"),
    "mgc_superblue19": ("0 0 5000 5000", "250 250 4750 4750"),
    
    # 特殊设计使用不同的 die size
    "mgc_des_perf_b": ("0 0 1200 1200", "120 120 1080 1080"),
    "mgc_fft_a": ("0 0 1500 1500", "150 150 1350 1350"),
    "mgc_fft_b": ("0 0 1500 1500", "150 150 1350 1350"),
    "mgc_matrix_mult_a": ("0 0 2000 2000", "200 200 1800 1800"),
    "mgc_matrix_mult_c": ("0 0 2000 2000", "200 200 1800 1800"),
}

# 默认 die size（如果设计不在配置中）
DEFAULT_DIE_SIZE = ("0 0 5000 5000", "250 250 4750 4750")


def get_die_size(design_name: str) -> Tuple[str, str]:
    """
    获取设计的 die size 配置
    
    Args:
        design_name: 设计名称（如 "mgc_fft_1"）
    
    Returns:
        (die_area_str, core_area_str) 元组
    """
    return DIE_SIZE_CONFIG.get(design_name, DEFAULT_DIE_SIZE)


def get_all_designs() -> List[str]:
    """
    获取所有已配置的设计名称
    
    Returns:
        设计名称列表
    """
    return list(DIE_SIZE_CONFIG.keys())

