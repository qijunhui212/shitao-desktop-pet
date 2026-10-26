# 师滔像素桌宠

基于 Python / PySide6 的 Windows 像素桌宠，包含肌肉态和微胖态、动作动画、头顶消息气泡和 OpenAI 兼容 API 对话。

这是 **1.5.2 功能分支的整理源码版（2026-10-26）**。仓库不包含个人聊天记录、账号凭据、真实人物知识库或本机音色试验。师滔是 AI 角色，模型回答不等于真人本人发言。

## 已包含

- 两套像素形态及切换、运动、群舞、皮套大笑、SIU、蛋白粉、DJ、敲代码、放鸽子等动作。
- 拖动、下落、摔倒和起身；可选动作菜单。
- 乳黄色聊天界面、角色头顶气泡、表情包与语义情绪状态。
- OpenAI 兼容接口配置、流式回复、可停止生成。
- 本机事件记忆导入与管理、有限频率的主动问话和自言自语。
- 每小时群记忆的存储、整理和检索源码；摘要供群内回复与桌宠私聊使用。

## 源码运行（Windows 10/11，Python 3.11 或 3.12）

~~~powershell
git clone https://github.com/qijunhui212/shitao-desktop-pet.git
cd shitao-desktop-pet
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe main.py
~~~

创建环境后也可双击 run.bat。首次启动自行填写 API Key、API 地址和模型名；这些值保存在本机 .env，被 Git 忽略。未配置 API 时仍可使用桌宠动作。

## 微信和每小时群记忆

普通桌宠可独立运行。仓库保留微信桥接和群记忆逻辑，但 **不附带可直接用于任何微信版本或任何账号的接入安装包**。原本机接入依赖特定版本的外部组件和本机密钥，这些都没有上传。

实验性接入需额外安装 requirements-wechat-bridge.txt，在本机配置 WECHAT_GROUP_ID 和 WECHAT_BRIDGE_RUNTIME，并自行准备匹配版本、通过自检的接入组件。没有组件时点击接入会明确提示未配置，不影响桌宠私聊。

启动监听后只收集目标群的新文字消息。开启群记忆会把待整理消息发送到你配置的聊天 API，每小时最多整理一次；空队列不调用 API，失败保留消息到下一小时。单次最多 200 条和约 12000 字符，超出部分排队；检索最多 4 条摘要和 1400 字符。摘要保存在本机 data/wechat_group_memory.sqlite3，不上传 GitHub。

在「微信群接入 → 查看群记忆」查看摘要和原消息出处。取消记忆开关后暂停新增收集与整理，已有摘要仍可回忆。

## 测试与本地打包

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-wechat-bridge.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm desktop_pet.spec
~~~

构建产物在 dist/DesktopPet/。必须分发完整目录，不能只拿走其中的 EXE。此仓库当前交付源码；尚未把本次源码更新发布为可安装的 GitHub Release。未签名程序在部分 Windows 系统可能受到应用控制拦截，本项目不要求关闭系统防护。

## 数据与素材

- data/、.env、数据库、微信密钥、安装目录、日志和语音模型均被排除。
- 默认角色只保留说话风格，具体人物经历请自行导入本机知识库。
- [LICENSE](LICENSE) 保留原项目 MIT 代码许可；图片、GIF、表情包和人物形象的权利说明见 [ASSET-NOTICE.md](ASSET-NOTICE.md)。
