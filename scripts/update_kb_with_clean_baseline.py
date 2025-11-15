#!/usr/bin/env python3
"""
更新知识库：添加EXP-002 Clean Baseline的OpenROAD数据

这个脚本会：
1. 读取现有知识库（27个案例，主要是DreamPlace数据）
2. 读取EXP-002的16个ISPD 2015设计的完整OpenROAD数据
3. 更新或添加这些设计的OpenROAD质量指标
4. 保存更新后的知识库
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import math

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_existing_kb(kb_path: Path) -> dict:
    """加载现有知识库"""
    if not kb_path.exists():
        return {"version": "1.0", "num_cases": 0, "cases": []}
    
    with open(kb_path, 'r') as f:
        return json.load(f)


def load_clean_baseline_results(results_dir: Path) -> dict:
    """加载EXP-002的所有结果"""
    results = {}
    
    for design_dir in results_dir.iterdir():
        if not design_dir.is_dir():
            continue
        
        result_file = design_dir / 'result.json'
        if not result_file.exists():
            continue
        
        with open(result_file, 'r') as f:
            data = json.load(f)
            if data.get('status') == 'success':
                results[data['design']] = data
    
    return results


def calculate_design_features(result: dict) -> list:
    """计算设计特征向量（与原有知识库格式一致）"""
    comp_count = result.get('component_count', 0)
    net_count = result.get('net_count', 0)
    
    # 对数变换（避免0）
    log_comp = math.log(comp_count + 1)
    log_net = math.log(net_count + 1)
    
    # 设计规模特征
    features = [
        log_comp / log_net if log_net > 0 else 0,  # component/net ratio
        log_comp,
        log_net,
        0.0,  # num_partitions (clean baseline无分区)
        0.0,  # num_boundary_nets
        0.0,  # avg_partition_size
        0.0,  # partition_balance
        math.log(result.get('legalized_hpwl', 0) + 1),  # log(hpwl)
        result.get('runtime_seconds', 0) / 60.0  # runtime in minutes
    ]
    
    return features


def update_case_in_kb(kb: dict, design_id: str, result: dict) -> bool:
    """更新知识库中的案例，或添加新案例"""
    
    # 查找是否已存在该设计
    existing_idx = None
    for idx, case in enumerate(kb['cases']):
        if case.get('design_id') == design_id:
            existing_idx = idx
            break
    
    # 准备新的质量指标
    quality_metrics = {
        "hpwl": result.get('legalized_hpwl'),
        "global_placement_hpwl": result.get('global_placement_hpwl'),
        "legalized_hpwl": result.get('legalized_hpwl'),
        "num_placed_components": result.get('component_count'),
        "num_components": result.get('component_count'),
        "num_nets": result.get('net_count'),
        "boundary_cost": 0.0,  # clean baseline无分区
        "runtime_seconds": result.get('runtime_seconds'),
        "num_modules": 0,  # clean baseline无分区
        "die_size": result.get('die_size_used', {}).get('die_area'),
        "core_area": result.get('die_size_used', {}).get('core_area'),
        "openroad_source": "EXP-002_clean_baseline",
        "timestamp": result.get('timestamp')
    }
    
    if existing_idx is not None:
        # 更新现有案例
        kb['cases'][existing_idx]['quality_metrics'].update(quality_metrics)
        kb['cases'][existing_idx]['features'] = calculate_design_features(result)
        kb['cases'][existing_idx]['timestamp'] = datetime.now().isoformat()
        return True
    else:
        # 添加新案例
        new_case = {
            "design_id": design_id,
            "features": calculate_design_features(result),
            "partition_strategy": {},  # clean baseline无分区策略
            "negotiation_patterns": {},
            "quality_metrics": quality_metrics,
            "timestamp": datetime.now().isoformat(),
            "embedding": [0.0] * 128  # 占位符，后续可用真实embedding
        }
        kb['cases'].append(new_case)
        return False


def main():
    # 路径配置
    kb_path = project_root / 'data' / 'knowledge_base' / 'kb_cases.json'
    results_dir = project_root / 'results' / 'clean_baseline'
    
    print("=" * 80)
    print("更新知识库：添加EXP-002 Clean Baseline数据")
    print("=" * 80)
    print()
    
    # 1. 加载现有知识库
    print(f"📖 加载现有知识库: {kb_path}")
    kb = load_existing_kb(kb_path)
    original_count = len(kb['cases'])
    print(f"   原有案例数: {original_count}")
    print()
    
    # 2. 加载Clean Baseline结果
    print(f"📊 加载Clean Baseline结果: {results_dir}")
    results = load_clean_baseline_results(results_dir)
    print(f"   成功加载: {len(results)} 个设计")
    print()
    
    # 3. 更新知识库
    print("🔄 更新知识库...")
    updated_count = 0
    added_count = 0
    
    for design_id, result in sorted(results.items()):
        is_update = update_case_in_kb(kb, design_id, result)
        if is_update:
            print(f"   ✅ 更新: {design_id}")
            print(f"      Legalized HPWL: {result.get('legalized_hpwl'):,.0f}")
            print(f"      运行时间: {result.get('runtime_seconds'):.1f}s")
            updated_count += 1
        else:
            print(f"   ➕ 新增: {design_id}")
            print(f"      Legalized HPWL: {result.get('legalized_hpwl'):,.0f}")
            print(f"      运行时间: {result.get('runtime_seconds'):.1f}s")
            added_count += 1
    
    # 4. 更新元数据
    kb['num_cases'] = len(kb['cases'])
    kb['last_updated'] = datetime.now().isoformat()
    kb['exp_002_integrated'] = True
    
    print()
    print(f"📝 更新统计:")
    print(f"   原有案例: {original_count}")
    print(f"   更新案例: {updated_count}")
    print(f"   新增案例: {added_count}")
    print(f"   最终案例数: {kb['num_cases']}")
    print()
    
    # 5. 保存更新后的知识库
    # 先备份原有知识库
    if kb_path.exists():
        backup_path = kb_path.parent / f"kb_cases_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        print(f"💾 备份原知识库: {backup_path.name}")
        with open(backup_path, 'w') as f:
            json.dump(load_existing_kb(kb_path), f, indent=2)
    
    print(f"💾 保存更新后的知识库: {kb_path}")
    with open(kb_path, 'w') as f:
        json.dump(kb, f, indent=2)
    
    print()
    print("=" * 80)
    print("✅ 知识库更新完成！")
    print("=" * 80)
    print()
    print("📊 知识库统计:")
    print(f"   - 总案例数: {kb['num_cases']}")
    print(f"   - OpenROAD完整数据: {len(results)} 个设计")
    print(f"   - 文件大小: {kb_path.stat().st_size / 1024:.1f} KB")
    print()


if __name__ == '__main__':
    main()
