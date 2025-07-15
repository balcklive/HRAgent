# Author: Peng Fei

import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from src.models import JobRequirement, RequirementConfirmationState, InteractionMessage
from src.prompts import (
    REQUIREMENT_CONFIRMATION_SYSTEM_PROMPT,
    REQUIREMENT_CONFIRMATION_INITIAL_PROMPT_TEMPLATE
)
import json
import re

class RequirementConfirmationNode:
    """需求确认节点 - 与HR交互确认招聘需求"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature, streaming=True)
        self.system_prompt = REQUIREMENT_CONFIRMATION_SYSTEM_PROMPT
        
    async def process_stream(self, state: RequirementConfirmationState, user_input: Optional[str] = None):
        """流式处理需求确认"""
        try:
            # 如果是第一次交互，基于JD生成初始问题
            if not state.conversation_history and not user_input:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=REQUIREMENT_CONFIRMATION_INITIAL_PROMPT_TEMPLATE.format(jd_text=state.jd_text))
                ]
                
                full_response = ""
                async for chunk in self.llm.astream(messages):
                    content = chunk.content
                    full_response += content
                    yield {
                        "type": "content",
                        "content": content,
                        "is_complete": False
                    }
                
                # 更新状态
                state.conversation_history.append(
                    InteractionMessage(role="assistant", content=full_response)
                )
                
                yield {
                    "type": "continue",
                    "content": "",
                    "is_complete": False
                }
                return
            
            # 处理用户输入
            if user_input:
                state.conversation_history.append(
                    InteractionMessage(role="user", content=user_input)
                )
            
            # 构建消息
            messages = self._build_messages(state, user_input)
            
            full_response = ""
            async for chunk in self.llm.astream(messages):
                content = chunk.content
                full_response += content
                
                yield {
                    "type": "content",
                    "content": content,
                    "is_complete": False
                }
            
            # 流式完成后，进行状态更新和完成判断
            completion_status = self._parse_completion_status(full_response)
            
            # 更新状态
            state.conversation_history.append(
                InteractionMessage(role="assistant", content=full_response)
            )
            
            if completion_status.get("status") == "complete":
                # 更新完成状态
                state.position = completion_status["position"]
                state.must_have = completion_status["must_have"]
                state.nice_to_have = completion_status["nice_to_have"]
                state.deal_breaker = completion_status["deal_breaker"]
                state.is_complete = True
                state.missing_info = []
                
                yield {
                    "type": "complete",
                    "content": "",
                    "is_complete": True,
                    "job_requirement": state.to_job_requirement().dict()
                }
            else:
                # 继续收集信息
                state.missing_info = completion_status.get("missing_info", [])
                yield {
                    "type": "continue",
                    "content": "",
                    "is_complete": False
                }
                
        except Exception as e:
            yield {
                "type": "error",
                "content": f"处理过程中发生错误: {str(e)}",
                "is_complete": False
            }
    
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
            HumanMessage(content=REQUIREMENT_CONFIRMATION_INITIAL_PROMPT_TEMPLATE.format(jd_text=jd_text))
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def _build_messages(self, state: RequirementConfirmationState, user_input: Optional[str] = None) -> List:
        """构建消息列表"""
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
        
        return messages
    
    def _generate_response(self, state: RequirementConfirmationState) -> str:
        """生成AI响应"""
        messages = self._build_messages(state)
        
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
            
            if result["is_complete"]:
                job_requirement = result["job_requirement"]
                print("=== 需求确认完成 ===")
                print(f"职位: {job_requirement.position}")
                print(f"必要条件: {job_requirement.must_have}")
                print(f"加分条件: {job_requirement.nice_to_have}")
                print(f"排除条件: {job_requirement.deal_breaker}")
                return job_requirement
        
        return None

def main():
    """测试函数"""
    # 示例JD
    jd_text = """
    我们正在招聘一名高级Python开发工程师，负责后端系统开发。
    要求：
    - 5年以上Python开发经验
    - 熟悉Django、Flask等框架
    - 有数据库设计和优化经验
    - 良好的团队协作能力
    - 有微服务架构经验优先
    - 熟悉Docker、Kubernetes优先
    """
    
    node = RequirementConfirmationNode()
    job_requirement = node.run_standalone(jd_text)
    
    if job_requirement:
        print("需求确认成功！")
    else:
        print("需求确认失败或中断")

if __name__ == "__main__":
    main()