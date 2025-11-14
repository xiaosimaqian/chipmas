# 基线实验运行说明

## 1. 代码同步状态

✅ **已同步到服务器**：
- `src/utils/openroad_interface.py` - 已修复GROUPS替换逻辑，支持多线程
- `scripts/run_baseline_experiments.py` - 批量运行脚本，已配置`threads="max"`
- `scripts/run_baseline_batch.py` - 按规模排序的批量运行脚本
- `scripts/start_baseline_batch.sh` - 后台启动脚本
- `scripts/check_baseline_status.sh` - 状态检查脚本

## 2. OpenROAD多线程配置

✅ **已配置多线程**：
- `OpenRoadInterface(threads="max")` 会传递 `-threads max` 参数给OpenROAD
- 代码位置：`src/utils/openroad_interface.py:904-913`

⚠️ **注意**：
- OpenROAD的某些阶段（如DEF解析、初始化）可能是单线程的
- 如果top显示CPU占用率100%（单核），可能是：
  1. OpenROAD正在执行单线程阶段
  2. 或者OpenROAD的某些算法本身就是单线程的
  3. 可以通过`htop`查看OpenROAD进程的线程数确认

## 3. 后台运行

✅ **已启动后台运行**：
```bash
# 在服务器上启动
ssh keqin@172.30.31.98
cd ~/chipmas
bash scripts/start_baseline_batch.sh
```

✅ **检查状态**：
```bash
# 本地执行
bash scripts/check_baseline_status.sh

# 或直接在服务器上
cd ~/chipmas
bash scripts/check_baseline_status.sh
```

## 4. 批量运行（按规模从小到大）

✅ **设计列表（已按组件数量排序）**：
1. mgc_pci_bridge32_b (28,920 个组件)
2. mgc_pci_bridge32_a (29,521 个组件)
3. mgc_fft_a (30,631 个组件)
4. mgc_fft_b (30,631 个组件)
5. mgc_fft_2 (32,281 个组件)
6. mgc_fft_1 (32,281 个组件)
7. mgc_des_perf_a (108,292 个组件)
8. mgc_des_perf_1 (112,644 个组件)
9. mgc_des_perf_b (112,644 个组件)
10. mgc_edit_dist_a (127,419 个组件)
11. mgc_matrix_mult_b (146,442 个组件)
12. mgc_matrix_mult_a (149,655 个组件)
13. mgc_matrix_mult_1 (155,325 个组件)
14. mgc_superblue16_a (680,538 个组件)
15. mgc_superblue11_a (925,010 个组件)
16. mgc_superblue12 (1,285,615 个组件)

## 5. 结果位置

- **实验结果**：`results/baseline/{design_name}/result.json`
- **布局DEF**：`results/ispd2015/{design_name}/layout_{timestamp}.def`
- **日志文件**：`results/baseline_logs/baseline_batch_{timestamp}.log`
- **汇总结果**：`results/baseline/summary.json`

## 6. 监控命令

```bash
# 查看最新日志
tail -f ~/chipmas/results/baseline_logs/baseline_batch_*.log

# 查看进程
ps aux | grep run_baseline

# 查看OpenROAD进程
ps aux | grep openroad

# 查看已完成的设计
find ~/chipmas/results/baseline -name "result.json" | wc -l

# 查看CPU和内存使用
top -p $(pgrep -f run_baseline_batch)
```

## 7. 注意事项

1. **内存使用**：OpenROAD对内存要求很高，大设计可能需要数十GB内存
2. **运行时间**：大设计（如superblue12）可能需要数小时
3. **并发限制**：建议不要同时运行多个OpenROAD进程，避免内存不足
4. **断点续传**：使用`--skip-existing`可以跳过已完成的设计


