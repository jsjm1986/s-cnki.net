import os
from typing import Dict, List
import logging
import json
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

class ArticleSummarizer:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("未设置DEEPSEEK_API_KEY环境变量")
            
        self.api_base = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat-7b"  # 使用DeepSeek的中文模型
        
    async def _call_api(self, messages: List[Dict], temperature: float = 0.7) -> str:
        """调用DeepSeek API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 2000,
                        "stream": False
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"调用DeepSeek API失败: {str(e)}")
            raise
    
    def _build_summary_prompt(self, content: Dict) -> str:
        """构建总结提示词"""
        return f"""你是一个专业的学术文献分析助手。请对以下中文学术文章进行深入分析和总结。

文章标题：{content.get('title', '未提供')}

文章摘要：
{content.get('abstract', '未提供')}

关键词：
{', '.join(content.get('keywords', ['未提供']))}

基金项目：
{content.get('fund', '未提供')}

请从以下几个方面进行分析：

1. 研究背景与意义
- 研究的理论和实践背景
- 研究的重要性和必要性

2. 研究方法与创新点
- 采用的主要研究方法
- 研究的创新之处
- 技术路线或实验设计

3. 主要研究发现
- 核心实验/研究结果
- 重要数据和发现
- 结果的可靠性分析

4. 研究结论与贡献
- 主要研究结论
- 理论贡献
- 实践意义

5. 研究局限性
- 研究的不足之处
- 潜在的问题和限制

6. 未来研究方向
- 值得进一步探索的问题
- 可能的研究扩展

请用专业、简洁的语言进行分析，突出文章的创新点和学术价值。
"""

    def _build_methodology_prompt(self, content: Dict) -> str:
        """构建研究方法分析提示词"""
        return f"""请详细分析这篇学术论文的研究方法和技术路线。

文章信息：
标题：{content.get('title', '未提供')}
摘要：{content.get('abstract', '未提供')}

请重点关注：
1. 研究方法的选择依据和合理性
2. 实验/研究设计的具体步骤
3. 数据收集和处理方法
4. 研究方法的创新点
5. 方法论可能存在的局限性

请用专业的角度进行分析，并指出方法上的优缺点。"""

    def _build_innovation_prompt(self, content: Dict) -> str:
        """构建创新点分析提示词"""
        return f"""请分析这篇学术论文的创新点和学术贡献。

文章信息：
标题：{content.get('title', '未提供')}
摘要：{content.get('abstract', '未提供')}
关键词：{', '.join(content.get('keywords', ['未提供']))}

请从以下方面进行分析：
1. 理论创新
2. 方法创新
3. 技术创新
4. 应用创新
5. 与现有研究的比较优势

请具体指出创新点及其价值。"""

    async def summarize(self, content: Dict) -> Dict:
        """生成全面的文献分析"""
        try:
            # 生成总体摘要
            summary_prompt = self._build_summary_prompt(content)
            summary = await self._call_api([{
                "role": "user",
                "content": summary_prompt
            }])

            # 分析研究方法
            methodology_prompt = self._build_methodology_prompt(content)
            methodology_analysis = await self._call_api([{
                "role": "user",
                "content": methodology_prompt
            }])

            # 分析创新点
            innovation_prompt = self._build_innovation_prompt(content)
            innovation_analysis = await self._call_api([{
                "role": "user",
                "content": innovation_prompt
            }])

            return {
                "summary": summary,
                "methodology_analysis": methodology_analysis,
                "innovation_analysis": innovation_analysis,
                "generated_at": datetime.now().isoformat(),
                "model_info": {
                    "model": self.model,
                    "version": "1.0"
                }
            }

        except Exception as e:
            logger.error(f"生成文献分析失败: {str(e)}")
            return {
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
            
    async def analyze_references(self, references: List[str]) -> str:
        """分析参考文献"""
        try:
            prompt = f"""请分析以下参考文献列表，总结该研究的文献综述情况：

参考文献：
{chr(10).join(f"{i+1}. {ref}" for i, ref in enumerate(references))}

请从以下方面进行分析：
1. 参考文献的时间分布
2. 核心参考文献及其贡献
3. 文献引用的完整性和全面性
4. 国内外研究现状对比
5. 可能存在的文献缺失领域

请给出专业的分析意见。"""

            return await self._call_api([{
                "role": "user",
                "content": prompt
            }])
            
        except Exception as e:
            logger.error(f"分析参考文献失败: {str(e)}")
            return f"分析参考文献时发生错误：{str(e)}" 