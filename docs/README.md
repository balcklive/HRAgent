# HR Agent 项目文档

## 文档目录

### 实施方案
- [流式输出实现方案](./streaming_implementation_plan.md) - 详细的流式输出技术方案和实施计划

### 项目结构
```
HRAgent/
├── docs/                           # 项目文档
│   ├── streaming_implementation_plan.md  # 流式输出实现方案
│   └── README.md                   # 文档索引
├── src/                            # 源代码
│   ├── nodes/                      # 工作流节点
│   │   └── requirement_confirmation_node.py  # 需求确认节点
│   ├── models/                     # 数据模型
│   └── workflow_optimized.py      # 优化后的工作流
├── web_interface/                  # Web界面
│   ├── app.py                      # FastAPI应用
│   ├── static/                     # 静态文件
│   └── templates/                  # HTML模板
└── examples/                       # 示例和测试
```

### 开发状态
- ✅ 基础聊天机器人界面完成
- ✅ 交互式需求确认完成
- ✅ 报告前端显示完成
- 📋 流式输出方案制定完成
- ⏳ 流式输出实现待开始

### 快速开始
1. 参考 [流式输出实现方案](./streaming_implementation_plan.md) 了解技术细节
2. 按照方案中的实施计划进行开发
3. 遇到问题时查看方案中的技术细节和参考资料

### 维护说明
- 请在实施过程中及时更新相关文档
- 记录实际遇到的问题和解决方案
- 补充新的技术方案和优化建议