# OpenROAD GUI 加载设计脚本说明

## 脚本说明

### 推荐使用：`load_design_gui.tcl` ⭐
**这是统一后的最佳版本**，包含：
- ✅ 自动检测 Verilog 文件
- ✅ 完整的错误处理
- ✅ 详细的加载进度提示
- ✅ 使用说明

### 其他脚本（可删除）

1. **`load_design_gui_simple.tcl`** 
   - 简化版，功能较少
   - 可以删除，已被 `load_design_gui.tcl` 替代

2. **`load_design_gui_verified.tcl`**
   - 验证版本，但功能不完整（没有处理 Verilog）
   - 可以删除，已被 `load_design_gui.tcl` 替代

## 为什么之前有两个脚本？

在修复 `get_design` 命令错误的过程中，创建了两个测试版本：
- `load_design_gui_verified.tcl` - 最简单的版本，用于验证基本功能
- `load_design_gui_simple.tcl` - 添加了 Verilog 支持

现在已统一为 `load_design_gui.tcl`，建议删除其他两个脚本。

## 使用方法

```bash
cd /Users/keqin/Documents/workspace/chip-rag/chipmas
openroad -gui scripts/load_design_gui.tcl
```

## 修改设计路径

编辑 `scripts/load_design_gui.tcl`，修改第 8 行：
```tcl
set design_dir "data/ispd2015/your_design_name"
```
