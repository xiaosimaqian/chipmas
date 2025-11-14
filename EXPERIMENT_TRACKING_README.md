# 实验跟踪系统使用说明

## 📋 快速开始

### 1. 登记新实验

```bash
python3 scripts/experiment_tracker.py register \
  --name "实验名称" \
  --purpose "实验目的描述" \
  --location "服务器/本地路径" \
  --script "运行的脚本或命令" \
  --output "产出目录" \
  --log "日志目录"
```

### 2. 启动实验

```bash
# 标记实验开始
python3 scripts/experiment_tracker.py start EXP-XXX --pid 12345
```

### 3. 完成实验

```bash
python3 scripts/experiment_tracker.py finish EXP-XXX \
  --status "✅ 完成" \
  --success 10 \
  --fail 3 \
  --total 13
```

### 4. 更新实验信息

```bash
# 添加关键发现
python3 scripts/experiment_tracker.py update EXP-XXX \
  --finding "关键发现描述"

# 添加问题
python3 scripts/experiment_tracker.py update EXP-XXX \
  --issue "遇到的问题"

# 添加后续行动
python3 scripts/experiment_tracker.py update EXP-XXX \
  --action "下一步计划"
```

### 5. 查看实验

```bash
# 列出所有实验
python3 scripts/experiment_tracker.py list

# 列出特定状态的实验
python3 scripts/experiment_tracker.py list --status "🚀 运行中"

# 显示实验详情
python3 scripts/experiment_tracker.py show EXP-XXX
```

## 📊 实验状态

- `⏳ 计划中` - 已登记但未开始
- `🚀 运行中` - 正在运行
- `✅ 完成` - 成功完成
- `⚠️ 部分成功` - 部分成功
- `❌ 失败` - 失败

## 🐍 Python API 使用

```python
from scripts.experiment_tracker import ExperimentTracker

tracker = ExperimentTracker()

# 登记实验
exp_id = tracker.register_experiment(
    name="我的实验",
    purpose="测试目的",
    location="本地",
    script="python test.py"
)

# 启动实验
tracker.start_experiment(exp_id, pid=12345)

# 完成实验
tracker.finish_experiment(
    exp_id,
    status="✅ 完成",
    success_count=5,
    fail_count=0,
    total_count=5,
    metrics={
        "HPWL": 123456,
        "Runtime": "2.5h"
    }
)

# 更新实验
tracker.update_experiment(
    exp_id,
    findings=["发现1", "发现2"],
    issues=["问题1"],
    next_actions=["行动1"]
)
```

## �� 文件说明

- `experiments.json` - 实验数据库（JSON格式）
- `scripts/experiment_tracker.py` - 实验跟踪工具
- `EXPERIMENTS.md` - 实验记录（Markdown格式，人类可读）

## 💡 最佳实践

1. **实验前登记**：实验开始前先登记，生成实验ID
2. **及时更新**：实验过程中及时更新关键信息
3. **完整记录**：记录PID、路径、指标、发现、问题、后续行动
4. **定期检查**：定期运行 `list` 命令查看实验状态
5. **数据备份**：定期备份 `experiments.json`

## 🎯 实验模板

```bash
# 1. 登记
EXP_ID=$(python3 scripts/experiment_tracker.py register \
  --name "XXX实验" \
  --purpose "测试XXX" \
  --location "服务器" \
  --script "run_xxx.py" | grep -oP 'EXP-\d+')

# 2. 启动
python3 scripts/experiment_tracker.py start $EXP_ID --pid $$

# 3. 运行你的实验
# ... 实验代码 ...

# 4. 完成
python3 scripts/experiment_tracker.py finish $EXP_ID \
  --status "✅ 完成" \
  --success 10 \
  --fail 0 \
  --total 10
```
