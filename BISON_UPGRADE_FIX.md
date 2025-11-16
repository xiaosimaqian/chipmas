# Bison版本升级修复

## 📋 问题

编译Yosys时遇到错误：
```
frontends/verilog/verilog_parser.y:36.10-14: 错误: require bison 3.6, but have 3.5.1
```

**原因**：Yosys需要bison ≥3.6，但系统只有3.5.1

## ✅ 快速解决方案

### 方法1：使用快速升级脚本（推荐）

```bash
ssh keqin@172.30.31.98
cd ~/chipmas
bash scripts/upgrade_bison.sh
```

脚本会自动：
1. 检查当前bison版本
2. 下载bison 3.8.2源码
3. 编译安装到`~/.local/bin`
4. 验证安装

### 方法2：手动升级

```bash
# 1. 安装依赖
sudo apt-get update
sudo apt-get install -y m4 wget

# 2. 下载bison源码
cd ~
wget https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.xz
tar -xf bison-3.8.2.tar.xz
cd bison-3.8.2

# 3. 编译安装
./configure --prefix=$HOME/.local
make -j$(nproc)
make install

# 4. 添加到PATH
export PATH=$HOME/.local/bin:$PATH
echo 'export PATH=$PATH:$HOME/.local/bin' >> ~/.bashrc
source ~/.bashrc

# 5. 验证
bison --version
```

## 🔄 升级后继续编译Yosys

升级bison后，重新运行Yosys安装脚本：

```bash
cd ~/chipmas
bash scripts/reinstall_yosys_from_source.sh
```

脚本会自动检测并使用新安装的bison（在`~/.local/bin`中）。

## ✅ 验证

升级完成后，验证bison版本：

```bash
bison --version
```

应该看到：
```
bison (GNU Bison) 3.8.2
```

## 📝 注意事项

1. **PATH优先级**：`~/.local/bin`应该在系统PATH之前，这样会优先使用新安装的bison
2. **永久生效**：将`export PATH=$PATH:$HOME/.local/bin`添加到`~/.bashrc`，确保每次登录都生效
3. **编译Yosys时**：确保PATH已更新，脚本会自动处理

## 🔗 相关文件

- `scripts/upgrade_bison.sh`：快速升级脚本
- `scripts/reinstall_yosys_from_source.sh`：Yosys安装脚本（已更新，自动检测bison版本）
- `scripts/YOSYS_REINSTALL_GUIDE.md`：详细安装指南

---

**创建时间**：2025-11-15  
**状态**：✅ 脚本已创建并同步到服务器

