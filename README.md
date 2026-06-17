# 🎓 Hardcore English Coach

一个基于 AI 的英语学习 Web 应用，帮助你在真实场景中练习英语口语和写作，并获得即时纠错反馈。

## ✨ 功能介绍

- 场景对话：模拟咖啡馆点餐、超市闲聊、工作面试等真实生活场景，与 AI 伙伴自由对话
- 实时语法纠错：对话过程中自动检测语法错误、不自然表达及中文夹杂，给出地道英文建议
- 多种 AI 人格：支持毒舌 Roast / 夸夸 Hype / 正常 Normal / 醉酒 Tipsy 四种对话风格，学习不无聊
- 日记批改：用英文写日记，AI 逐句分析并给出修改建议
- 错题本：自动收录每次对话中的错误，方便复习回顾
- 生词本：查询单词释义、例句和中文翻译，一键收藏

## 🛠️ 技术栈

- 前端 / 框架：Python + Streamlit
- AI 接口：DeepSeek API
- 数据库：SQLite（本地持久化存储学习记录）
- 部署：Streamlit Cloud

## 🚀 本地运行

1. 克隆仓库

```bash
git clone https://github.com/bai213/my-english-coach.git
cd my-english-coach
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置 API Key

在项目根目录创建 `.streamlit/secrets.toml` 文件：

```toml
DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
```

4. 启动应用

```bash
streamlit run app.py
```

## 📸 项目截图

> 场景对话界面，支持实时语法纠错与多种 AI 人格切换

## 📄 License

MIT
