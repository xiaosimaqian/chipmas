# 服务器端Step 1-4复现指南

## 📋 目标

在服务器上安装Yosys并复现Step 1-4，确保本地和服务器状态一致。

## 🔧 步骤1：安装Yosys

### 方法1：使用apt安装（推荐）

```bash
ssh keqin@172.30.31.98
sudo apt-get update
sudo apt-get install -y yosys
yosys -V
```

### 方法2：从源码编译

如果无法使用sudo，参考：`scripts/YOSYS_SERVER_INSTALL.md`

## 📦 步骤2：同步代码

代码已同步到服务器：`~/chipmas/`

如需重新同步：
```bash
# 在本地运行
cd /path/to/chipmas
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='tests/results' \
    --exclude='results' \
    --exclude='data' \
    . keqin@172.30.31.98:~/chipmas/
```

## ✅ 步骤3：运行Step 1-4测试

### 方法1：使用测试脚本（推荐）

```bash
ssh keqin@172.30.31.98
cd ~/chipmas
bash scripts/run_step1_4_server.sh
```

### 方法2：手动运行

```bash
ssh keqin@172.30.31.98
cd ~/chipmas

python3 scripts/run_partition_based_flow.py \
    --design mgc_fft_1 \
    --design-dir data/ispd2015/mgc_fft_1 \
    --kspecpart-dir results/kspecpart/mgc_fft_1 \
    --output-dir tests/results/partition_flow/mgc_fft_1_server \
    --partitions 4 \
    --skip-openroad
```

## 📊 验证结果

测试完成后，检查以下文件：

1. **flow_summary.json**：`tests/results/partition_flow/mgc_fft_1_server/flow_summary.json`
2. **分区网表**：`tests/results/partition_flow/mgc_fft_1_server/hierarchical_netlists/partition_*.v`
3. **顶层网表**：`tests/results/partition_flow/mgc_fft_1_server/hierarchical_netlists/top.v`
4. **Formal验证报告**：`tests/results/partition_flow/mgc_fft_1_server/formal_verification/verification_report.json`

### 检查命令

```bash
ssh keqin@172.30.31.98
cd ~/chipmas

# 检查Step 1-4状态
python3 << 'PYEOF'
import json
from pathlib import Path

summary_file = Path("tests/results/partition_flow/mgc_fft_1_server/flow_summary.json")
if summary_file.exists():
    summary = json.load(open(summary_file))
    print("=== Step 1-4完成状态 ===")
    for step_name, step_data in summary.get('steps', {}).items():
        if isinstance(step_data, dict):
            status = step_data.get('status', 'unknown')
            print(f"  {step_name}: {status}")
PYEOF

# 检查Formal验证结果
python3 << 'PYEOF'
import json
from pathlib import Path

report_file = Path("tests/results/partition_flow/mgc_fft_1_server/formal_verification/verification_report.json")
if report_file.exists():
    report = json.load(open(report_file))
    print(f"\n=== Formal验证结果 ===")
    print(f"成功: {report.get('success')}")
    print(f"等价: {report.get('equivalent')}")
    if report.get('equivalent'):
        print("✅ Formal验证通过：flatten网表与hierarchical网表功能等价！")
PYEOF
```

## 🔍 预期结果

### Step 1-4状态

- ✅ `kspecpart`: completed
- ✅ `verilog_partition`: completed
- ✅ `formal_verification`: passed（或failed但继续执行）
- ✅ `physical_mapping`: completed

### Formal验证结果

- ✅ `success: True`
- ✅ `equivalent: True`
- ✅ **结论：flatten网表与hierarchical网表功能等价！**

## 📝 注意事项

1. **Yosys安装**：需要sudo权限或从源码编译
2. **Python环境**：确保服务器上有Python 3和必要的依赖
3. **文件路径**：确保设计文件和K-SpecPart结果文件存在
4. **Formal验证**：如果Yosys未安装，Formal验证会跳过

## 🐛 故障排除

### 问题1：Yosys未安装
**解决**：参考`scripts/YOSYS_SERVER_INSTALL.md`

### 问题2：缺少Python依赖
**解决**：
```bash
pip3 install -r requirements.txt
```

### 问题3：找不到设计文件
**解决**：确保数据已同步到服务器

---

**创建时间**：2025-11-15  
**服务器**：172.30.31.98

