# ISPD 2015设计批量运行指南

## 📋 概述

本指南说明如何在所有ISPD 2015设计上运行完整的Step 1-8流程。

**总设计数**: 16个（不包括已完成的mgc_fft_1）

**预计总运行时间**: 3-6小时（取决于设计大小）

---

## 🎯 任务1：在本地OpenROAD GUI查看mgc_fft_1布局

### ✅ 已完成！文件已下载到本地

**查看方法**:

```bash
cd /Users/keqin/Documents/workspace/chip-rag/chipmas/local_view/mgc_fft_1
openroad -gui view_layout.tcl
```

**详细说明**: 查看 `/Users/keqin/Documents/workspace/chip-rag/chipmas/local_view/mgc_fft_1/README.md`

---

## 🎯 任务2：在其他15个ISPD 2015设计上运行完整测试

### 方案选择

有两种方案：

#### 🔸 方案A：完全自动化（推荐）

**适用场景**: K-SpecPart分区文件已存在

**步骤**:

1. 同步脚本到服务器：

```bash
cd /Users/keqin/Documents/workspace/chip-rag/chipmas
rsync -avz scripts/run_all_ispd2015_complete.sh keqin@172.30.31.98:~/chipmas/scripts/
```

2. 在服务器上运行：

```bash
ssh keqin@172.30.31.98
cd ~/chipmas
nohup bash scripts/run_all_ispd2015_complete.sh > /tmp/ispd2015_batch.log 2>&1 &

# 记录进程ID
echo $!

# 监控进度
tail -f /tmp/ispd2015_batch.log
```

3. 检查进度（随时）：

```bash
# 查看最新日志
tail -100 /tmp/ispd2015_batch.log

# 查看已完成的设计
ls -lh ~/chipmas/tests/results/partition_flow/ | grep step1_8

# 检查进程是否还在运行
ps aux | grep run_all_ispd2015_complete
```

#### 🔸 方案B：分两步（需要先运行K-SpecPart）

**适用场景**: K-SpecPart分区文件不存在（大多数设计）

**步骤**:

**Step B.1: 批量运行K-SpecPart分区**

```bash
# 同步脚本
rsync -avz scripts/run_kspecpart_batch.sh keqin@172.30.31.98:~/chipmas/scripts/

# 在服务器上运行
ssh keqin@172.30.31.98
cd ~/chipmas
nohup bash scripts/run_kspecpart_batch.sh > /tmp/kspecpart_batch.log 2>&1 &

# 监控进度
tail -f /tmp/kspecpart_batch.log
```

**预计时间**: 1-3小时（15个设计）

**Step B.2: 批量运行Step 1-8**

等待K-SpecPart完成后：

```bash
cd ~/chipmas
nohup bash scripts/run_all_ispd2015_complete.sh > /tmp/ispd2015_batch.log 2>&1 &

# 监控进度
tail -f /tmp/ispd2015_batch.log
```

**预计时间**: 2-4小时（15个设计）

---

## 📊 结果收集

### 运行完成后

批量运行会生成以下文件：

```
logs/step1_8_batch_YYYYMMDD_HHMMSS/
├── summary.json          # JSON格式汇总
├── REPORT.md            # Markdown格式报告
├── mgc_fft_2.log        # 各设计的详细日志
├── mgc_fft_a.log
├── ...
└── mgc_superblue16_a.log
```

### 查看汇总结果

```bash
# 在服务器上
cd ~/chipmas
cat logs/step1_8_batch_*/REPORT.md

# 或查看JSON
cat logs/step1_8_batch_*/summary.json | python3 -m json.tool
```

### 下载结果到本地

```bash
# 在本地执行
cd /Users/keqin/Documents/workspace/chip-rag/chipmas

# 下载汇总结果
rsync -avz keqin@172.30.31.98:~/chipmas/logs/step1_8_batch_*/ local_results/

# 下载所有OpenROAD布局结果（可选，文件较大）
rsync -avz keqin@172.30.31.98:~/chipmas/tests/results/partition_flow/*_step1_8/ local_view/
```

---

## 🔍 监控和调试

### 实时监控

```bash
# 在另一个终端
watch -n 60 'ls ~/chipmas/tests/results/partition_flow/ | grep step1_8 | wc -l'
```

### 检查特定设计的失败原因

```bash
# 查看失败设计的日志
tail -100 ~/chipmas/logs/step1_8_batch_*/mgc_fft_2.log

# 检查OpenROAD错误
grep -i "error" ~/chipmas/logs/step1_8_batch_*/mgc_fft_2.log

# 检查Python异常
grep -i "traceback" ~/chipmas/logs/step1_8_batch_*/mgc_fft_2.log
```

### 重新运行失败的设计

```bash
cd ~/chipmas

# 单独运行某个设计
python3 scripts/run_partition_based_flow.py \
    --design mgc_fft_2 \
    --verilog data/ispd2015/mgc_fft_2/design.v \
    --num-partitions 4 \
    --output-dir tests/results/partition_flow/mgc_fft_2_step1_8
```

---

## 📈 预期结果

基于mgc_fft_1的成功经验，预期：

| 指标 | 预期范围 |
|------|---------|
| 边界代价 (BC) | 0.001% - 1% |
| Internal HPWL | 取决于设计大小 |
| Boundary HPWL | 远小于Internal HPWL |
| 单个设计运行时间 | 6-30分钟 |
| Formal验证 | 全部通过 |

---

## ⚠️ 注意事项

1. **磁盘空间**: 每个设计的结果约100-500MB，确保有足够空间（~10GB）
2. **内存使用**: 大设计可能需要16GB+内存
3. **并行运行**: 当前脚本是串行的。如需并行，需修改脚本
4. **OpenROAD超时**: 超大设计可能超时（默认无超时限制）
5. **K-SpecPart依赖**: 需要Julia环境和CPLEX许可证

---

## 🚀 快速开始（立即运行）

如果您想立即开始批量运行：

```bash
# 1. 同步所有脚本到服务器
cd /Users/keqin/Documents/workspace/chip-rag/chipmas
rsync -avz scripts/*.sh keqin@172.30.31.98:~/chipmas/scripts/

# 2. SSH到服务器
ssh keqin@172.30.31.98

# 3. 进入工作目录
cd ~/chipmas

# 4. 先运行K-SpecPart批量分区（如果需要）
nohup bash scripts/run_kspecpart_batch.sh > /tmp/kspecpart_batch.log 2>&1 &
echo "K-SpecPart PID: $!"

# 5. 等待K-SpecPart完成（或在新终端）后运行完整流程
# nohup bash scripts/run_all_ispd2015_complete.sh > /tmp/ispd2015_batch.log 2>&1 &
# echo "Step1-8 PID: $!"

# 6. 监控日志
tail -f /tmp/kspecpart_batch.log
# 或
# tail -f /tmp/ispd2015_batch.log
```

---

## 📞 问题排查

### 问题1：K-SpecPart失败

**症状**: `ERROR: Could not solve MIP problem`

**解决**: 检查CPLEX许可证，或尝试使用hMETIS作为备选

### 问题2：OpenROAD超时或内存不足

**症状**: 进程被杀死 (OOM Killer)

**解决**: 
- 增加swap空间
- 或跳过超大设计
- 或使用更少的partitions

### 问题3：Yosys formal验证失败

**症状**: `equivalent=False`

**解决**: 
- 检查Yosys版本（需要≥0.56）
- 查看详细日志
- 可能是VerilogPartitioner的bug，需要调试

---

## 📝 脚本说明

| 脚本 | 功能 | 用途 |
|------|------|------|
| `run_kspecpart_batch.sh` | 批量运行K-SpecPart分区 | 为所有设计生成分区文件 |
| `run_all_ispd2015_complete.sh` | 完整批量流程（假设K-SpecPart已完成） | 运行Step 1-8 |
| `run_step1_8_server.sh` | 单个设计的Step 1-8 | 单独测试 |

---

**最后更新**: 2025-11-16  
**作者**: AI Assistant

