# Yosys从GitHub源码重新安装指南

## 📋 概述

本指南用于在服务器上卸载当前Yosys版本，并从[GitHub源码](https://github.com/YosysHQ/yosys)安装最新版本。

## 🎯 为什么需要重新安装？

根据分析，Yosys 0.9版本在Formal验证时无法正确证明输出端口等价性，而Yosys 0.56及更新版本可以正常工作。

## 📦 前置要求

### 必需依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    git \
    make \
    build-essential \
    g++ \
    clang \
    m4 \
    wget
```

**重要**：Bison版本要求≥3.6

- 如果系统bison版本<3.6，需要从源码编译升级
- 可以使用快速升级脚本：`bash scripts/upgrade_bison.sh`
- 或手动从源码编译（见故障排除部分）

### 推荐依赖（可选但推荐）

```bash
sudo apt-get install -y \
    libreadline-dev \
    tcl-dev \
    libffi-dev \
    graphviz \
    xdot
```

## 🚀 安装步骤

### 方法1：使用自动安装脚本（推荐）

```bash
ssh keqin@172.30.31.98
cd ~/chipmas
bash scripts/reinstall_yosys_from_source.sh
```

脚本会自动：
1. 检测并卸载当前Yosys版本
2. 检查编译依赖
3. 从GitHub克隆最新源码（包含submodules）
4. 配置编译环境
5. 编译Yosys（10-20分钟）
6. 安装到 `~/.local/bin/yosys`
7. 验证安装

### 方法2：手动安装

如果自动脚本遇到问题，可以手动执行：

```bash
# 1. 卸载当前Yosys
sudo apt-get remove -y yosys
sudo apt-get purge -y yosys
rm -f ~/.local/bin/yosys

# 2. 克隆源码（包含submodules）
cd ~
git clone --recurse-submodules https://github.com/YosysHQ/yosys.git yosys_build
cd yosys_build

# 3. 配置编译环境
make config-gcc  # 或 make config-clang

# 4. 编译（使用所有CPU核心）
make -j$(nproc)

# 5. 安装
mkdir -p ~/.local/bin
ln -sf ~/yosys_build/yosys ~/.local/bin/yosys

# 6. 添加到PATH（如果还没有）
export PATH=$PATH:$HOME/.local/bin
echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc

# 7. 验证
yosys -V
```

## ✅ 验证安装

安装完成后，验证Yosys版本：

```bash
yosys -V
```

应该看到类似输出：
```
Yosys 0.59.1 (git sha1 ..., ...)
```

**重要**：确保版本号 ≥ 0.56

## 🔄 重新运行测试

安装完成后，重新运行Step 1-4测试：

```bash
cd ~/chipmas
bash scripts/run_step1_4_server.sh
```

应该看到：
```
✅ Formal验证通过：flatten ≈ hierarchical
```

## 🐛 故障排除

### 问题1：编译失败 - Bison版本过低

**错误**：`require bison 3.6, but have 3.5.1`

**解决**：

**方法1：使用快速升级脚本（推荐）**
```bash
cd ~/chipmas
bash scripts/upgrade_bison.sh
```

**方法2：手动升级bison**
```bash
# 安装依赖
sudo apt-get install -y m4 wget

# 下载bison源码
cd ~
wget https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.xz
tar -xf bison-3.8.2.tar.xz
cd bison-3.8.2

# 编译安装
./configure --prefix=$HOME/.local
make -j$(nproc)
make install

# 添加到PATH
export PATH=$HOME/.local/bin:$PATH
echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc
source ~/.bashrc

# 验证
bison --version
```

### 问题2：编译失败 - 缺少依赖

**错误**：`fatal error: readline/readline.h: No such file or directory`

**解决**：
```bash
sudo apt-get install -y libreadline-dev
```

### 问题3：编译失败 - 缺少submodules

**错误**：`fatal error: libs/cxxopts/include/cxxopts.hpp: No such file or directory`

**解决**：
```bash
cd ~/yosys_build
git submodule update --init --recursive
```

### 问题3：找不到yosys命令

**错误**：`command not found: yosys`

**解决**：
```bash
# 检查是否在PATH中
echo $PATH | grep -q ".local/bin" || export PATH=$PATH:$HOME/.local/bin

# 或添加到 ~/.bashrc
echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc
source ~/.bashrc
```

### 问题4：编译时间过长

**说明**：Yosys编译通常需要10-20分钟，这是正常的。如果超过30分钟，可能是：
- CPU性能较低
- 编译并行度设置过高（可以降低 `-j` 参数）

## 📚 参考文档

- [Yosys GitHub仓库](https://github.com/YosysHQ/yosys)
- [Yosys官方文档](https://yosys.readthedocs.io/)
- [Building from Source](https://yosys.readthedocs.io/en/latest/getting_started.html#building-from-source)

## 📝 版本要求

根据测试结果：
- ✅ **Yosys ≥ 0.56**：Formal验证正常工作
- ❌ **Yosys 0.9**：Formal验证失败（无法证明输出端口等价性）

**推荐**：使用最新稳定版本（当前为0.59.1）

---

**创建时间**：2025-11-15  
**适用环境**：Linux服务器（Ubuntu/Debian）

