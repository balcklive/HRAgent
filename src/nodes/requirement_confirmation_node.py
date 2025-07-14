from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from src.models import (
    RequirementConfirmationState,
    InteractionMessage,
    JobRequirement
)
import json
import re

class RequirementConfirmationNode:
    """需求确认节点 - 与HR交互确认招聘需求"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """你是一个专业的HR助手，负责帮助HR明确招聘需求。

**你的任务：**
1. 基于用户提供的JD（职位描述），与HR进行对话确认招聘需求
2. 收集并分类招聘需求为三个维度：
   - 必要条件 (must_have): 候选人必须满足的条件
   - 加分条件 (nice_to_have): 有则更好的条件
   - 排除条件 (deal_breaker): 绝对不能接受的条件

**对话规则：**
1. 始终使用中文与HR交流
2. 主动询问不明确的信息
3. 确认每个条件属于哪个维度
4. 询问具体的技能要求、经验年限、教育背景等
5. 确保信息完整准确

**判断完成标准：**
- 职位名称明确
- 至少有3个必要条件
- 至少有2个加分条件
- 至少有1个排除条件
- 没有模糊不清的表述

**输出格式：**
当信息收集完成时，输出JSON格式的确认信息：
```json
{
    "status": "complete",
    "position": "职位名称",
    "must_have": ["必要条件1", "必要条件2", ...],
    "nice_to_have": ["加分条件1", "加分条件2", ...],
    "deal_breaker": ["排除条件1", "排除条件2", ...],
    "summary": "需求总结"
}
```

如果信息不完整，输出：
```json
{
    "status": "incomplete",
    "missing_info": ["缺失的信息1", "缺失的信息2", ...],
    "next_question": "下一个要问的问题"
}
```"""

    def process(self, state: RequirementConfirmationState, user_input: Optional[str] = None) -> Dict[str, Any]:
        """处理需求确认流程"""
        try:
            # 如果是第一次交互，基于JD生成初始问题
            if not state.conversation_history and not user_input:
                response = self._generate_initial_question(state.jd_text)
                return self._update_state(state, "assistant", response)
            
            # 处理用户输入
            if user_input:
                state.conversation_history.append(
                    InteractionMessage(role="user", content=user_input)
                )
            
            # 生成AI响应
            response = self._generate_response(state)
            
            # 解析响应判断是否完成
            completion_status = self._parse_completion_status(response)
            
            if completion_status.get("status") == "complete":
                # 更新状态信息
                state.position = completion_status["position"]
                state.must_have = completion_status["must_have"]
                state.nice_to_have = completion_status["nice_to_have"]
                state.deal_breaker = completion_status["deal_breaker"]
                state.is_complete = True
                state.missing_info = []
                
                return {
                    "status": "success",
                    "message": response,
                    "job_requirement": state.to_job_requirement(),
                    "is_complete": True
                }
            else:
                # 继续收集信息
                state.missing_info = completion_status.get("missing_info", [])
                return {
                    "status": "continue",
                    "message": response,
                    "is_complete": False,
                    "missing_info": state.missing_info
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"处理过程中发生错误: {str(e)}",
                "is_complete": False
            }
    
    def _generate_initial_question(self, jd_text: str) -> str:
        """基于JD生成初始问题"""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
这是一个职位描述：

{jd_text}

请分析这个JD，然后开始与HR确认具体的招聘需求。首先询问最重要的信息。
""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def _generate_response(self, state: RequirementConfirmationState) -> str:
        """生成AI响应"""
        messages = [SystemMessage(content=self.system_prompt)]
        
        # 添加JD信息
        messages.append(HumanMessage(content=f"职位描述：{state.jd_text}"))
        
        # 添加对话历史
        for msg in state.conversation_history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # 添加当前状态信息
        current_info = f"""
当前收集到的信息：
- 职位：{state.position or '未确定'}
- 必要条件：{state.must_have or '未确定'}
- 加分条件：{state.nice_to_have or '未确定'}
- 排除条件：{state.deal_breaker or '未确定'}
- 缺失信息：{state.missing_info or '未确定'}

请根据当前信息继续询问或完成确认。
"""
        messages.append(HumanMessage(content=current_info))
        
        response = self.llm.invoke(messages)
        
        # 更新对话历史
        state.conversation_history.append(
            InteractionMessage(role="assistant", content=response.content)
        )
        
        return response.content
    
    def _parse_completion_status(self, response: str) -> Dict[str, Any]:
        """解析响应中的完成状态"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有JSON格式，假设还未完成
            return {
                "status": "incomplete",
                "next_question": "请继续提供更多信息"
            }
            
        except json.JSONDecodeError:
            return {
                "status": "incomplete",
                "next_question": "请继续提供更多信息"
            }
    
    def _update_state(self, state: RequirementConfirmationState, role: str, content: str) -> Dict[str, Any]:
        """更新状态并返回结果"""
        state.conversation_history.append(
            InteractionMessage(role=role, content=content)
        )
        
        return {
            "status": "continue",
            "message": content,
            "is_complete": False
        }
    
    def run_standalone(self, jd_text: str) -> JobRequirement:
        """独立运行模式"""
        state = RequirementConfirmationState(jd_text=jd_text)
        
        print("=== HR招聘需求确认系统 ===")
        print(f"职位描述：{jd_text}\n")
        
        # 生成初始问题
        result = self.process(state)
        print(f"AI助手: {result['message']}\n")
        
        # 交互循环
        while not state.is_complete:
            user_input = input("HR: ")
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("会话结束")
                break
                
            result = self.process(state, user_input)
            print(f"AI助手: {result['message']}\n")
            
            if result.get('is_complete'):
                print("=== 需求确认完成 ===")
                return result['job_requirement']
        
        # 如果未完成就退出，返回当前状态
        return state.to_job_requirement()


# 使用示例
if __name__ == "__main__":
    # 示例JD
    jd_text = """
    高级后端开发工程师
    
    岗位职责：
    - 负责核心交易系统的架构设计和开发
    - 设计高并发、高可用的微服务系统
    - 优化系统性能，处理大规模数据
    
    任职要求：
    - 5年以上后端开发经验
    - 熟练掌握Node.js、Python等语言
    - 有分布式系统设计经验
    - 了解Docker、Kubernetes
    """
    
    node = RequirementConfirmationNode()
    job_requirement = node.run_standalone(jd_text)
    print(f"最终需求: {job_requirement}")