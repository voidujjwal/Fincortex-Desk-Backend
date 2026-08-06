from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_news
from tradingagents.dataflows.config import get_config

MAX_TOOL_ROUNDS = 6


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
        ]

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(query, start_date, end_date) tool to search for company-specific news and social media discussions. Try to look at all sources possible from social media to sentiment to news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        rounds = int(state.get("social_rounds") or 0) + 1
        from langchain_core.messages import HumanMessage
        if rounds <= MAX_TOOL_ROUNDS:
            result = chain.invoke(state["messages"])
            if result.tool_calls:
                return {
                    "messages": [result],
                    "sentiment_report": "",
                    "social_rounds": rounds,
                }
            if not (result.content or ""):
                # Model bailed without calling tools — retry once with a
                # forceful instruction so data gathering cannot be skipped.
                result = chain.invoke(
                    state["messages"]
                    + [
                        HumanMessage(
                            "Do not answer yet. You MUST call the available tools "
                            "to gather data before writing your report."
                        )
                    ]
                )
                if result.tool_calls:
                    return {
                        "messages": [result],
                        "sentiment_report": "",
                        "social_rounds": rounds,
                    }
        else:
            result = llm.invoke(
                state["messages"]
                + [
                    HumanMessage(
                        "Tool data gathering is complete. Now write your "
                        "comprehensive detailed report (markdown) based on the "
                        "tool data gathered so far. Do not call any tools."
                    )
                ]
            )

        report = result.content
        if isinstance(report, list):
            report = "\n".join(
                block.get("text", "")
                for block in report
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if not report:
            tool_parts = [
                str(m.content)
                for m in state["messages"]
                if getattr(m, "type", "") == "tool" and m.content
            ]
            if tool_parts:
                report = "\n\n".join(tool_parts[-3:])
        if not report and rounds > MAX_TOOL_ROUNDS:
            report = "Analysis report unavailable for this run."

        return {
            "messages": [result],
            "sentiment_report": report,
            "social_rounds": rounds,
        }

    return social_media_analyst_node
