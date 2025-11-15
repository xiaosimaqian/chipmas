#!/usr/bin/env julia
###############################################################################
# K-SpecPart测试脚本
# 
# 用法: julia scripts/test_kspecpart.jl <hgr_file> <num_parts> <imbalance> <output_file>
#
# 示例:
#   julia scripts/test_kspecpart.jl results/kspecpart/mgc_fft_1.hgr 4 0.05 results/kspecpart/mgc_fft_1.part.4
###############################################################################

# 添加K-SpecPart路径
push!(LOAD_PATH, joinpath(@__DIR__, "..", "external", "HypergraphPartitioning", "K_SpecPart"))

# 导入K-SpecPart模块
include(joinpath(@__DIR__, "..", "external", "HypergraphPartitioning", "K_SpecPart", "specpart.jl"))

using .SpecPart

function run_kspecpart(hgr_file::String, num_parts::Int, imbalance::Float64, output_file::String)
    """
    运行K-SpecPart进行超图分区
    
    参数:
        hgr_file: 超图文件路径 (.hgr格式)
        num_parts: 分区数量
        imbalance: 不平衡因子 (0-1之间)
        output_file: 输出分区结果文件
    """
    
    println("="^80)
    println("K-SpecPart 超图分区")
    println("="^80)
    println("输入文件: $hgr_file")
    println("分区数: $num_parts")
    println("不平衡因子: $imbalance")
    println("输出文件: $output_file")
    println("="^80)
    println()
    
    # 检查输入文件
    if !isfile(hgr_file)
        error("输入文件不存在: $hgr_file")
    end
    
    # 读取超图
    println("正在读取超图...")
    hgraph = SpecPart.read_hypergraph(hgr_file)
    println("  顶点数: ", length(hgraph.vertex_weights))
    println("  超边数: ", length(hgraph.edge_weights))
    println()
    
    # 运行K-SpecPart
    println("正在运行K-SpecPart...")
    partition = SpecPart.k_way_spectral_partition(
        hgraph,
        num_parts,
        imbalance,
        eigen_vecs=2,
        refine_iters=2,
        solver_iters=40,
        best_solns=5,
        ncycles=2,
        seed=0
    )
    println()
    
    # 评估分区质量
    println("正在评估分区质量...")
    cutsize, balance = SpecPart.golden_evaluator(hgraph, num_parts, partition)
    println("  Cutsize: $cutsize")
    println("  Balance: $balance")
    println()
    
    # 保存结果
    println("正在保存结果到: $output_file")
    mkpath(dirname(output_file))
    open(output_file, "w") do f
        for p in partition
            println(f, p)
        end
    end
    
    println()
    println("="^80)
    println("✓ K-SpecPart完成!")
    println("="^80)
    
    return cutsize, balance
end

# 主函数
function main()
    if length(ARGS) < 4
        println("用法: julia test_kspecpart.jl <hgr_file> <num_parts> <imbalance> <output_file>")
        println()
        println("示例:")
        println("  julia test_kspecpart.jl results/kspecpart/mgc_fft_1.hgr 4 0.05 results/kspecpart/mgc_fft_1.part.4")
        exit(1)
    end
    
    hgr_file = ARGS[1]
    num_parts = parse(Int, ARGS[2])
    imbalance = parse(Float64, ARGS[3])
    output_file = ARGS[4]
    
    try
        run_kspecpart(hgr_file, num_parts, imbalance, output_file)
    catch e
        println("✗ 错误: $e")
        Base.show_backtrace(stdout, catch_backtrace())
        exit(1)
    end
end

# 运行主函数
if abspath(PROGRAM_FILE) == @__FILE__
    main()
end

