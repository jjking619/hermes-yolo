# Hermes + YOLOv8n 视觉识别（H1 板）

在 H1 板（aarch64, Debian 13）上部署 Hermes Agent + YOLOv8n 视觉识别，已实测验证。

## 一、安装 Hermes（约 10 分钟）

```bash
sudo apt update && sudo apt install -y curl
# 清华源加速依赖下载；--skip-browser 跳过浏览器（YOLO 用不到，省 428MB）
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- \
  --skip-browser --skip-computer-use
 #卡在 setup 向导：Ctrl+C 跳过即可（不影响使用）
source ~/.bashrc #在终端生效
hermes doctor   # 验证安装
```

## 二、配置 API key

```bash
# (1) .env 写入 key（systemd 不支持行尾注释，不要加 #）
cat > ~/.hermes/.env << 'EOF'
OPENAI_API_KEY="sk-你的key"
EOF

# (2) config.yaml 配置（api_key 必须显式设置，否则 hermes 用 no-key-required 占位）
hermes config set model.provider custom
hermes config set model.base_url "https://你的API网关/v1"
hermes config set model.api_key "sk-你的key"
hermes config set model.default deepseek-v4-flash
```

## 三、部署 YOLO 工具

```bash
# 1. 进入项目目录
cd ~/hermes-yolo

# 2. 一键安装（自动装 YOLO 依赖 + 注册 MCP，幂等可重复跑）
bash install.sh
```

## 四、使用

```bash
hermes chat -q "test.jpg 里有什么"   # 一次性查询
hermes                            # 交互式会话
```

实测输出：`1 辆公交车（87.3%）、4 个行人（86.5%/85.4%/82.5%/26.7%）`

## 文件

| 文件 | 说明 |
|------|------|
| `yolo_tool.py` | YOLO 检测命令行工具（输出 JSON） |
| `yolo_mcp.py` | MCP stdio 服务器（Hermes 调用 YOLO 的桥梁） |
| `install.sh` | 一键安装脚本（装依赖 + 注册 MCP） |
| `yolov8n.pt` | YOLOv8n 模型 |
| `test.jpg` | 测试图片 |

## 常见问题

| 问题 | 解决 |
|------|------|
| 报 401 / key invalid | `model.api_key` 必须显式设置（.env 不会自动生效于 custom provider） |
| 安装卡在 Playwright | hermes 安装时加 `--skip-browser --skip-computer-use` |
| pip3 报 not found | `python3 -m pip install --upgrade --force-reinstall pip` |
