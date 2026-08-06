from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
)
from tradingagents.dataflows.config import get_config

MAX_TOOL_ROUNDS = 6


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
        ]

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements.",
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

        rounds = int(state.get("fundamentals_rounds") or 0) + 1
        from langchain_core.messages import HumanMessage
        if rounds <= MAX_TOOL_ROUNDS:
            result = chain.invoke(state["messages"])
            if result.tool_calls:
                return {
                    "messages": [result],
                    "fundamentals_report": "",
                    "fundamentals_rounds": rounds,
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
                        "fundamentals_report": "",
                        "fundamentals_rounds": rounds,
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
            "fundamentals_report": report,
            "fundamentals_rounds": rounds,
        }

    return fundamentals_analyst_node
