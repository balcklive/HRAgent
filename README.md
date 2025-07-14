# HR智能体简历筛选系统

基于LangGraph构建的多智能体HR简历筛选系统，通过智能对话确认招聘需求，自动解析简历，生成个性化评分维度，并输出结构化的候选人对比分析表格。

## 系统特性

- **交互式需求确认**: 智能对话收集精确的招聘需求
- **动态评分维度**: 根据职位自动生成个性化评分标准
- **批量异步处理**: 高效处理多份简历文件
- **精准评分系统**: 10分制评分，支持✓/⚠️/❌状态标记
- **Markdown报告**: 直观的表格对比格式输出

## 核心架构

### 五个智能体节点

1. **需求确认节点** (RequirementConfirmationNode)
   - 基于JD与HR交互确认招聘需求
   - 收集必要条件、加分条件、排除条件
   - 支持独立运行和集成调用

2. **评分维度生成节点** (ScoringDimensionNode)
   - 基于招聘需求生成个性化评分维度
   - 自动分配权重，支持4-6个评分维度
   - 适配不同职位类型

3. **简历结构化节点** (ResumeStructureNode)
   - 异步批量处理PDF/Word/Text格式简历
   - 智能提取基本信息、技能、经验等
   - 支持多种文件格式解析

4. **候选人评分节点** (CandidateEvaluationNode)
   - 基于个性化维度进行10分制评分
   - 自动匹配必要条件和加分条件
   - 生成详细评分理由和建议

5. **报告生成节点** (ReportGenerationNode)
   - 生成Markdown格式对比表格
   - 动态表格结构，支持多维度对比
   - 包含排名、推荐建议、优劣势分析

## 安装使用

### 快速开始

使用自动化设置脚本：

```bash
# Linux/macOS
./setup.sh

# Windows
setup.bat
```

### 环境要求

- Python 3.8+
- OpenAI API Key
- [uv](https://docs.astral.sh/uv/) (推荐的Python包管理工具，比pip快10-100倍)

### 安装uv

如果您还没有安装uv，请先安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用pip安装
pip install uv
```

### 安装依赖

```bash
# 创建虚拟环境并安装依赖（推荐）
uv sync

# 生成锁定文件（首次设置）
uv lock

# 或者直接安装到当前环境
uv pip install -e .

# 添加新依赖
uv add package-name

# 添加开发依赖
uv add --group dev package-name
```

### 环境配置

创建 `.env` 文件：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 使用方法

#### 1. 命令行模式

```bash
# 运行完整工作流
python main.py --jd examples/jd.txt --resumes examples/resume1.pdf examples/resume2.docx examples/resume3.txt
```

#### 2. 交互式模式

```bash
python main.py --interactive
```

在交互式模式中，您可以：
- 单独运行需求确认
- 单独运行简历结构化
- 运行完整工作流

#### 3. 独立节点使用

```python
from src.nodes import RequirementConfirmationNode

# 需求确认
node = RequirementConfirmationNode()
job_requirement = node.run_standalone(jd_text)
```

### 开发环境设置

```bash
# 克隆项目
git clone <repository-url>
cd HRAgent

# 安装开发依赖
uv sync --group dev

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

# 运行测试
uv run pytest

# 代码格式化
uv run black src/
uv run isort src/

# 类型检查
uv run mypy src/
```

#### 使用Makefile快捷命令

项目提供了Makefile来简化常用操作：

```bash
# 查看所有可用命令
make help

# 设置开发环境
make setup

# 安装依赖
make install

# 运行测试
make test

# 代码格式化
make format

# 运行所有检查
make check

# 运行示例
make run-example

# 交互式运行
make run-interactive
```

## 项目结构

```
HRAgent/
├── src/
│   ├── models/           # 数据模型定义
│   ├── nodes/            # 智能体节点实现
│   ├── utils/            # 工具类
│   └── workflow.py       # LangGraph工作流
├── examples/             # 示例文件
├── tests/               # 测试文件
├── main.py              # 主应用程序
├── requirements.txt     # 依赖列表
└── README.md           # 说明文档
```

## 输出示例

系统会生成类似以下格式的Markdown表格：

```markdown
## 基本信息对比

| **Basic Info** | **候选人A** | **候选人B** | **候选人C** |
|----------------|-------------|-------------|-------------|
| **Ranking** | 1 | 2 | 3 |
| **Overall Score** | 8.5/10 | 7.2/10 | 6.8/10 |
| **Recommendation** | 推荐 ✓ | 推荐 ✓ | 考虑 ⚠️ |

## 技能匹配 (40%权重)

| **技能匹配** | **候选人A** | **候选人B** | **候选人C** |
|-------------|-------------|-------------|-------------|
| **Node.js** | 6年经验 ✓ | 4年经验 ✓ | 2年经验 ⚠️ |
| **PostgreSQL** | 专家级 ✓ | 高级 ✓ | 中级 ⚠️ |
| **微服务** | 有经验 ✓ | 有经验 ✓ | 无经验 ❌ |
```

## 配置说明

### 支持的文件格式

- PDF (.pdf)
- Word文档 (.docx, .doc)
- 文本文件 (.txt)

### 评分标准

- **9-10分**: 完全符合要求，表现优秀
- **7-8分**: 基本符合要求，表现良好
- **5-6分**: 部分符合要求，表现一般
- **3-4分**: 不太符合要求，表现较差
- **1-2分**: 基本不符合要求，表现很差
- **0分**: 完全不符合要求或触发排除条件

### 状态标记

- **✓ (PASS)**: 7分以上，符合要求
- **⚠️ (WARNING)**: 4-6分，需要注意
- **❌ (FAIL)**: 3分以下，不符合要求

## 扩展开发

### 添加新的智能体节点

1. 在 `src/nodes/` 下创建新的节点类
2. 实现 `process()` 方法
3. 在 `src/workflow.py` 中集成新节点
4. 更新 `src/nodes/__init__.py`

### 自定义评分维度

可以通过修改 `ScoringDimensionNode` 来添加特定行业的评分维度模板。

### 支持新的文件格式

在 `src/utils/resume_parser.py` 中添加新的文件解析方法。

## 故障排除

### 常见问题

1. **API Key错误**: 检查 `.env` 文件中的 `OPENAI_API_KEY` 配置
2. **文件解析失败**: 确保简历文件格式正确且可读
3. **内存不足**: 减少 `max_concurrent` 参数值
4. **网络连接问题**: 检查网络连接和API访问权限

### 日志调试

系统会输出详细的执行日志，包括：
- 各节点的执行状态
- 文件解析结果
- 评分过程信息
- 错误详情

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交代码
4. 创建 Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。