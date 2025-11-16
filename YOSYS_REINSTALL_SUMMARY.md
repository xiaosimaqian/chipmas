# Yosys重新安装总结

## 📋 完成的工作

已创建完整的Yosys重新安装方案，用于在服务器上卸载旧版本并从GitHub源码安装最新版本。

## 📦 创建的文件

1. **`scripts/reinstall_yosys_from_source.sh`**
   - 自动安装脚本
   - 功能：
     - 自动检测并卸载当前Yosys版本
     - 检查编译依赖
     - 从GitHub克隆最新源码（使用`--recurse-submodules`）
     - 配置编译环境（自动选择gcc或clang）
     - 并行编译（使用所有CPU核心）
     - 安装到`~/.local/bin/yosys`
     - 验证安装

2. **`scripts/YOSYS_REINSTALL_GUIDE.md`**
   - 详细安装指南
   - 包含：
     - 前置要求
     - 自动安装步骤
     - 手动安装步骤
     - 故障排除
     - 参考文档

3. **`README.md`**（已更新）
   - 添加了Yosys版本要求说明
   - 添加了服务器安装指引

## 🎯 使用方法

### 在服务器上执行

```bash
ssh keqin@172.30.31.98
cd ~/chipmas
bash scripts/reinstall_yosys_from_source.sh
```

### 脚本执行流程

1. **卸载当前Yosys**
   - 检测安装方式（apt或手动）
   - 删除可执行文件和符号链接
   - 清理旧的编译目录

2. **检查依赖**
   - 必需：git, make, g++/clang++
   - 推荐：libreadline-dev, tcl-dev, libffi-dev

3. **克隆源码**
   - 使用`git clone --recurse-submodules`确保所有依赖都被克隆
   - 参考：[Yosys GitHub仓库](https://github.com/YosysHQ/yosys)

4. **编译安装**
   - 自动选择编译器（gcc或clang）
   - 并行编译（`-j$(nproc)`）
   - 安装到`~/.local/bin`

5. **验证**
   - 检查版本号（应≥0.56）
   - 验证可执行性

## ✅ 预期结果

安装完成后：
- Yosys版本：≥ 0.56（最新稳定版本0.59.1）
- 安装位置：`~/.local/bin/yosys`
- Formal验证：应能正常工作

## 🔄 后续步骤

安装完成后，重新运行测试：

```bash
cd ~/chipmas
bash scripts/run_step1_4_server.sh
```

应该看到：
```
✅ Formal验证通过：flatten ≈ hierarchical
```

## 📚 参考

- [Yosys GitHub仓库](https://github.com/YosysHQ/yosys)
- [Yosys官方文档](https://yosys.readthedocs.io/)
- `FORMAL_VERIFICATION_VERSION_ANALYSIS.md`：版本差异分析

---

**创建时间**：2025-11-15  
**状态**：✅ 脚本已创建并同步到服务器，等待执行

