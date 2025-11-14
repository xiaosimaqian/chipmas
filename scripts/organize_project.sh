#!/bin/bash
# 项目目录整理脚本
# 按照 chipmasrag.plan.md 1.1节的目录结构设计进行整理

set -e

CHIPMAS_DIR="/Users/keqin/Documents/workspace/chip-rag/chipmas"
cd "$CHIPMAS_DIR"

echo "======================================"
echo "ChipMASRAG 项目目录整理"
echo "======================================"

# 1. 创建归档目录（保存临时文件）
echo "[1/6] 创建归档目录..."
mkdir -p archive/scripts
mkdir -p archive/docs
mkdir -p archive/logs

# 2. 移动临时日志文件到归档
echo "[2/6] 归档临时日志文件..."
if [ -f "issue_report_20251112_224122.txt" ]; then
    mv issue_report_20251112_224122.txt archive/logs/
fi
if [ -f "monitor_baseline_20251112_223547.log" ]; then
    mv monitor_baseline_20251112_223547.log archive/logs/
fi

# 3. 清理scripts/下的临时baseline脚本（保留核心脚本）
echo "[3/6] 清理scripts/目录..."

# 3.1 保留的核心脚本
KEEP_SCRIPTS=(
    "build_kb.py"
    "convert_ispd2015_to_hgr.py"
    "run_titan23_openroad.sh"
)

# 3.2 移动baseline相关临时脚本到归档
BASELINE_SCRIPTS=(
    "auto_fix_and_restart.sh"
    "batch_expand_kb_all_benchmarks.py"
    "build_kb_from_dreamplace.py"
    "check_baseline_status.sh"
    "generate_baseline_data.py"
    "monitor_baseline.sh"
    "periodic_check.sh"
    "process_existing_dreamplace_results.py"
    "quick_check.sh"
    "report_issues.sh"
    "run_all_baselines.sh"
    "run_baseline_batch.py"
    "run_baseline_experiments.py"
    "run_baseline_parallel.py"
    "run_baseline_sequential.py"
    "run_clean_openroad.py"
    "run_dreamplace_batch.py"
    "start_all_benchmarks.sh"
    "start_baseline_batch.sh"
    "update_dreamplace_hpwl.py"
    "summary_mgc_pci_bridge32_b.md"
    "README_BASELINE.md"
    "README_build_kb.md"
    "README_load_design.md"
)

for script in "${BASELINE_SCRIPTS[@]}"; do
    if [ -f "scripts/$script" ]; then
        mv "scripts/$script" "archive/scripts/"
        echo "  已归档: scripts/$script"
    fi
done

# 3.3 移动测试脚本到归档
TEST_SCRIPTS=(
    "test_gui_load.sh"
    "test_openroad_interface.py"
    "view_titan23_gui.sh"
    "load_design_gui.tcl"
    "load_titan23_gui.tcl"
    "test_load_design.tcl"
    "query_kb.py"
)

for script in "${TEST_SCRIPTS[@]}"; do
    if [ -f "scripts/$script" ]; then
        mv "scripts/$script" "archive/scripts/"
        echo "  已归档: scripts/$script"
    fi
done

# 4. 清理docs/下的临时文件
echo "[4/6] 清理docs/目录..."

# 4.1 保留主要文档
KEEP_DOCS=(
    "chipmasrag.plan.md"
    "baseline_partitioning.md"
    "kspecpart_integration.md"
)

# 4.2 归档LaTeX编译产物
if [ -f "docs/ChipMASRAG_paper_cn.aux" ]; then
    mv docs/ChipMASRAG_paper_cn.* archive/docs/ 2>/dev/null || true
    mv docs/ChipMASRAG.bib archive/docs/ 2>/dev/null || true
    mv docs/ChipMASRAG_Architecture.tex archive/docs/ 2>/dev/null || true
    echo "  已归档: LaTeX相关文件"
fi

# 5. 创建缺失的核心模块占位文件
echo "[5/6] 创建缺失的核心模块..."

# 5.1 创建 src/ 核心模块
if [ ! -f "src/framework.py" ]; then
    cat > src/framework.py << 'EOF'
"""
ChipMASRAG 主框架
集成所有组件，提供统一接口
"""

class ChipMASRAG:
    """ChipMASRAG主框架类"""
    
    def __init__(self, config):
        """初始化框架"""
        self.config = config
        # TODO: 初始化各组件
        
    def run(self, design):
        """运行布局优化"""
        # TODO: 实现
        pass
        
    def train(self, designs):
        """训练模型"""
        # TODO: 实现
        pass
        
    def evaluate(self, design):
        """评估性能"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: src/framework.py"
fi

if [ ! -f "src/coordinator.py" ]; then
    cat > src/coordinator.py << 'EOF'
"""
协调者智能体
统一RAG检索、全局协调、奖励分配
"""

class CoordinatorAgent:
    """协调者智能体"""
    
    def __init__(self, config):
        """初始化协调者"""
        self.config = config
        # TODO: 初始化PPO策略网络
        
    def retrieve_rag(self, design_features, top_k=10):
        """执行RAG检索并广播结果"""
        # TODO: 实现
        pass
        
    def coordinate(self, agents):
        """全局协调各分区智能体"""
        # TODO: 实现
        pass
        
    def compute_global_reward(self):
        """计算全局奖励"""
        # TODO: 实现
        pass
        
    def update(self):
        """PPO训练更新"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: src/coordinator.py"
fi

if [ ! -f "src/partition_agent.py" ]; then
    cat > src/partition_agent.py << 'EOF'
"""
分区智能体
局部优化、边界协商、策略执行
"""

class PartitionAgent:
    """分区智能体"""
    
    def __init__(self, agent_id, config):
        """初始化分区智能体"""
        self.agent_id = agent_id
        self.config = config
        # TODO: 初始化GAT、Actor、Critic、协商网络
        
    def encode_state(self, state):
        """GAT状态编码"""
        # TODO: 实现
        pass
        
    def select_action(self, state):
        """Actor网络输出动作"""
        # TODO: 实现
        pass
        
    def negotiate(self, boundary_modules, rag_results):
        """知识驱动的边界协商"""
        # TODO: 实现
        pass
        
    def update(self, experiences):
        """MADDPG训练更新"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: src/partition_agent.py"
fi

if [ ! -f "src/training.py" ]; then
    cat > src/training.py << 'EOF'
"""
训练模块
MADDPG（分区智能体）和PPO（协调者）训练
"""

class MADDPGTrainer:
    """分区智能体训练器"""
    
    def __init__(self, agents, config):
        """初始化MADDPG训练器"""
        self.agents = agents
        self.config = config
        # TODO: 初始化经验回放缓冲区等
        
    def train_step(self, experiences):
        """执行一步训练"""
        # TODO: 实现
        pass


class PPOTrainer:
    """协调者训练器"""
    
    def __init__(self, coordinator, config):
        """初始化PPO训练器"""
        self.coordinator = coordinator
        self.config = config
        
    def train_step(self, trajectories):
        """执行一步训练"""
        # TODO: 实现
        pass


class TrainingManager:
    """统一训练管理器"""
    
    def __init__(self, framework, config):
        """初始化训练管理器"""
        self.framework = framework
        self.config = config
        
    def train(self, designs):
        """训练模型"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: src/training.py"
fi

# 5.2 创建 experiments/ 模块
if [ ! -f "experiments/runner.py" ]; then
    cat > experiments/runner.py << 'EOF'
"""
实验运行器
统一实验入口，管理实验生命周期
"""

class ExperimentRunner:
    """实验运行器"""
    
    def __init__(self, config):
        """初始化实验运行器"""
        self.config = config
        
    def run_experiment(self, design_name):
        """运行单个设计"""
        # TODO: 实现
        pass
        
    def run_benchmark(self, benchmark_name):
        """运行基准测试"""
        # TODO: 实现
        pass
        
    def run_ablation(self, design_name, variants):
        """运行消融实验"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: experiments/runner.py"
fi

if [ ! -f "experiments/evaluator.py" ]; then
    cat > experiments/evaluator.py << 'EOF'
"""
评估器
计算评估指标
"""

class Evaluator:
    """评估器"""
    
    def __init__(self, config):
        """初始化评估器"""
        self.config = config
        
    def calculate_boundary_cost(self, partition_layouts, partition_scheme):
        """计算边界代价"""
        # TODO: 实现
        pass
        
    def calculate_partition_balance(self, partition_scheme):
        """计算分区平衡度"""
        # TODO: 实现
        pass
        
    def calculate_negotiation_success_rate(self, negotiation_history):
        """计算协商成功率"""
        # TODO: 实现
        pass
        
    def calculate_partition_quality_score(self, partition_result):
        """计算分区质量评分"""
        # TODO: 实现
        pass
        
    def calculate_layout_quality_score(self, layout_result):
        """计算最终布局质量评分"""
        # TODO: 实现
        pass
        
    def evaluate_partition_layout_correlation(self, results):
        """评估分区质量与布局质量的相关性"""
        # TODO: 实现
        pass
EOF
    echo "  已创建: experiments/evaluator.py"
fi

if [ ! -f "experiments/logger.py" ]; then
    cat > experiments/logger.py << 'EOF'
"""
实验日志系统
完整记录实验过程
"""

import json
import logging
from pathlib import Path
from datetime import datetime

class ExperimentLogger:
    """实验日志系统"""
    
    def __init__(self, experiment_name, output_dir):
        """初始化日志系统"""
        self.experiment_name = experiment_name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / f"{experiment_name}_{self.timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志文件
        self.log_file = self.output_dir / "experiment.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(experiment_name)
        
    def log_config(self, config):
        """记录实验配置"""
        config_file = self.output_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        self.logger.info(f"配置已保存: {config_file}")
        
    def log_result(self, result):
        """记录实验结果"""
        result_file = self.output_dir / "results.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        self.logger.info(f"结果已保存: {result_file}")
        
    def log_checkpoint(self, checkpoint, step):
        """记录模型检查点"""
        checkpoint_dir = self.output_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        # TODO: 保存检查点
        pass
EOF
    echo "  已创建: experiments/logger.py"
fi

# 5.3 创建新增的工具模块
if [ ! -f "src/utils/hierarchical_transformation.py" ]; then
    cat > src/utils/hierarchical_transformation.py << 'EOF'
"""
层级化改造模块
将扁平网表转换为层次化网表（顶层+分区）
"""

def perform_hierarchical_transformation(design, partition_scheme):
    """
    层级化改造（K-SpecPart和ChipMASRAG共用）
    
    输入：
    - design: 原始扁平设计
    - partition_scheme: {component_name: partition_id}
    
    输出：
    - top_netlist: 顶层网表
    - partition_netlists: 各分区网表
    - verification_passed: 功能等价性验证结果
    """
    # TODO: 实现
    pass


def verify_functional_equivalence(original_flat_netlist, hierarchical_netlists):
    """
    使用Yosys进行Formal验证
    
    验证：原始扁平网表 ≡ (顶层网表 + 分区网表)
    """
    # TODO: 实现
    pass
EOF
    echo "  已创建: src/utils/hierarchical_transformation.py"
fi

if [ ! -f "src/utils/physical_mapping.py" ]; then
    cat > src/utils/physical_mapping.py << 'EOF'
"""
物理位置优化模块
基于分区间连接性优化物理位置映射
"""

def optimize_physical_layout(partition_scheme, boundary_nets):
    """
    优化逻辑分区到物理位置的映射
    
    目标：连接数多的分区应该物理相邻
    """
    # TODO: 实现
    pass


def analyze_partition_connectivity(partition_scheme, design):
    """
    分析分区间连接性
    
    返回：connectivity_matrix[(i,j)] = 分区i和j之间的跨分区连接数
    """
    # TODO: 实现
    pass
EOF
    echo "  已创建: src/utils/physical_mapping.py"
fi

if [ ! -f "src/utils/macro_lef_generator.py" ]; then
    cat > src/utils/macro_lef_generator.py << 'EOF'
"""
Macro LEF生成模块
从分区布局生成abstract LEF（macro定义）
"""

def generate_partition_macro_lef(part_id, partition_layout, physical_region):
    """
    从分区布局生成abstract LEF（macro定义）
    
    用于顶层OpenROAD，将分区作为宏单元
    """
    # TODO: 实现
    pass


def extract_boundary_pins(partition_layout, part_id):
    """
    从分区布局中提取边界引脚
    """
    # TODO: 实现
    pass
EOF
    echo "  已创建: src/utils/macro_lef_generator.py"
fi

# 6. 创建公共流程模块
echo "[6/6] 创建公共流程模块..."
mkdir -p experiments/common

if [ ! -f "experiments/common/__init__.py" ]; then
    touch experiments/common/__init__.py
fi

if [ ! -f "experiments/common/flow.py" ]; then
    cat > experiments/common/flow.py << 'EOF'
"""
公共流程模块
K-SpecPart和ChipMASRAG的共同流程（阶段3-9）
"""

def run_common_flow(design, partition_scheme, method="ChipMASRAG"):
    """
    公共流程（阶段3-9）
    
    两种方法在这里完全相同
    
    输入：
    - design: 设计对象
    - partition_scheme: 分区方案（来自K-SpecPart或ChipMASRAG）
    - method: 方法名称（用于日志）
    
    输出：
    - 完整结果（包括边界代价、HPWL等）
    """
    print(f"开始运行 {method} 公共流程...")
    
    # 阶段3: 层级化改造
    from src.utils.hierarchical_transformation import perform_hierarchical_transformation
    hierarchical = perform_hierarchical_transformation(design, partition_scheme)
    print("✅ 阶段3: 层级化改造完成")
    
    # 阶段4: 物理位置优化
    from src.utils.physical_mapping import optimize_physical_layout
    physical_mapping = optimize_physical_layout(
        partition_scheme, 
        hierarchical['boundary_nets']
    )
    print("✅ 阶段4: 物理位置优化完成")
    
    # 阶段5-9: OpenROAD布局和评估
    # TODO: 实现各分区OpenROAD、macro LEF生成、顶层OpenROAD、边界代价计算
    
    return {
        'method': method,
        'partition_scheme': partition_scheme,
        'hierarchical': hierarchical,
        'physical_mapping': physical_mapping,
        # 'boundary_cost': boundary_cost,
        # 'hpwl': hpwl
    }
EOF
    echo "  已创建: experiments/common/flow.py"
fi

echo ""
echo "======================================"
echo "整理完成！"
echo "======================================"
echo ""
echo "已归档文件位置: archive/"
echo "  - archive/scripts/  (临时脚本)"
echo "  - archive/docs/     (临时文档)"
echo "  - archive/logs/     (临时日志)"
echo ""
echo "新创建的核心模块:"
echo "  - src/framework.py"
echo "  - src/coordinator.py"
echo "  - src/partition_agent.py"
echo "  - src/training.py"
echo "  - src/utils/hierarchical_transformation.py"
echo "  - src/utils/physical_mapping.py"
echo "  - src/utils/macro_lef_generator.py"
echo "  - experiments/runner.py"
echo "  - experiments/evaluator.py"
echo "  - experiments/logger.py"
echo "  - experiments/common/flow.py"
echo ""
echo "保留的scripts:"
for script in "${KEEP_SCRIPTS[@]}"; do
    echo "  - scripts/$script"
done
echo ""


