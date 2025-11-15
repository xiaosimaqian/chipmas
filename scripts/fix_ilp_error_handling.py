#!/usr/bin/env python3
"""
修复K-SpecPart的optimal_attempt_partitioner.jl中的ILP错误处理
在ILP调用周围添加try-catch，失败时回退到hMETIS
"""

import re
from pathlib import Path

def fix_ilp_error_handling(file_path: Path):
    """在ILP调用周围添加错误处理"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 第一处修改：num_parts == 2的情况（约63行）
    # 查找模式：run(ilp_command, wait = true) 后面跟着 pfile = ...
    pattern1 = r'(        ilp_command = `sh -c \$ilp_string`\n)(        run\(ilp_command, wait = true\)\n)(        pfile = )'
    
    replacement1 = r'''\1        # Wrap ILP execution in try-catch to handle CPLEX issues
        ilp_success = false
        try
            run(ilp_command, wait = true)
            ilp_success = true
        catch e
            @warn "ILP solver failed (CPLEX license issue), falling back to hMETIS" exception=(e,)
        end
        
\3'''
    
    content = re.sub(pattern1, replacement1, content)
    
    # 修改balance检查部分，确保在ILP失败时也使用hMETIS
    pattern2 = r'(        \(cutsize, ~\) = golden_evaluator\(hgraph, num_parts, partition\)\n)(        if check_balance.*false \|\| cutsize == 0\n)'
    
    replacement2 = r'''\1\2            # Also use hMETIS if ILP was not successful
            ilp_success = false
        end
        
        if !ilp_success
'''
    
    content = re.sub(pattern2, replacement2, content)
    
    # 第二处修改：num_parts > 2的情况（约101行）
    # 类似的模式
    pattern3 = r'(    elseif \(hgraph\.num_hyperedges < 300 && num_parts > 2\)\n        ilp_string = .*\n        ilp_command = `sh -c \$ilp_string`\n)(        run\(ilp_command, wait = true\)\n)'
    
    replacement3 = r'''\1        # Wrap ILP execution in try-catch
        try
            run(ilp_command, wait = true)
        catch e
            @warn "ILP solver failed (CPLEX license issue), falling back to hMETIS" exception=(e,)
            # Fallback to hMETIS immediately
            runs = 10
            ctype = 1
            rtype = 1
            vcycle = 1
            reconst = 0
            dbglvl = 0
            hmetis_string = hmetis_path * " " * hgr_file_name * " " * string(num_parts) * " " * string(ub_factor) * " " * string(runs) * " " * string(ctype) * " " * string(rtype) * " " * string(vcycle) * " " * string(reconst) * " " * string(dbglvl)
            hmetis_command = `sh -c $hmetis_string`
            run(hmetis_command, wait=true)
        end
'''
    
    content = re.sub(pattern3, replacement3, content)
    
    # 备份原文件
    backup_path = file_path.with_suffix('.jl.bak2')
    with open(backup_path, 'w') as f:
        f.write(open(file_path).read())
    
    # 写入修改后的内容
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ 已修复 {file_path}")
    print(f"   备份保存至: {backup_path}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        # 默认路径
        file_path = Path.home() / 'chipmas/external/HypergraphPartitioning/K_SpecPart/optimal_attempt_partitioner.jl'
    
    fix_ilp_error_handling(file_path)

