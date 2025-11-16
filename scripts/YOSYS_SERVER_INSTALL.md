# 服务器上安装Yosys指南

## 方法1：使用apt安装（推荐，需要sudo权限）

```bash
ssh keqin@172.30.31.98
sudo apt-get update
sudo apt-get install -y yosys
yosys -V
```

## 方法2：从源码编译（不需要sudo权限）

如果无法使用sudo，可以从源码编译：

```bash
ssh keqin@172.30.31.98

# 1. 安装编译依赖（需要sudo）
sudo apt-get update
sudo apt-get install -y build-essential git libreadline-dev tcl-dev libffi-dev graphviz xdot pkg-config python3 python3-pip

# 2. 克隆Yosys源码
cd ~
git clone https://github.com/YosysHQ/yosys.git yosys_build
cd yosys_build

# 3. 初始化submodules
git submodule update --init --recursive

# 4. 编译（需要10-20分钟）
make config-gcc
make -j$(nproc)

# 5. 添加到PATH
echo 'export PATH=$PATH:~/yosys_build' >> ~/.bashrc
source ~/.bashrc

# 6. 验证
~/yosys_build/yosys -V
```

## 方法3：使用自动安装脚本

```bash
# 在本地运行
cd /path/to/chipmas
bash scripts/sync_and_test_step1_4_server.sh
```

脚本会自动：
1. 同步代码到服务器
2. 尝试安装Yosys
3. 运行Step 1-4测试

## 验证安装

```bash
ssh keqin@172.30.31.98
which yosys
yosys -V
```

## 常见问题

### 问题1：缺少readline库
```
fatal error: readline/readline.h: 没有那个文件或目录
```
**解决**：`sudo apt-get install -y libreadline-dev`

### 问题2：缺少git submodules
```
Initialize the submodule: Run 'git submodule update --init' to set up 'abc' as a submodule.
```
**解决**：`cd ~/yosys_build && git submodule update --init --recursive`

### 问题3：缺少cxxopts
```
fatal error: libs/cxxopts/include/cxxopts.hpp: 没有那个文件或目录
```
**解决**：确保已运行`git submodule update --init --recursive`

