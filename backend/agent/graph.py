from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import extract_node, classify_node, compare_node, report_node, error_node

MAX_RETRIES = 3


def _route(state: AgentState) -> str:
    if state.get("error"):
        if state.get("retry_count", 0) < MAX_RETRIES:
            return "retry"
        return "fail"
    return "continue"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("extract", extract_node)
    g.add_node("classify", classify_node)
    g.add_node("compare", compare_node)
    g.add_node("report", report_node)
    g.add_node("error", error_node)

    g.set_entry_point("extract")

    g.add_conditional_edges("extract", _route, {
        "continue": "classify",
        "retry": "extract",
        "fail": "error",
    })
    g.add_conditional_edges("classify", _route, {
        "continue": "compare",
        "retry": "classify",
        "fail": "error",
    })
    g.add_conditional_edges("compare", _route, {
        "continue": "report",
        "retry": "compare",
        "fail": "error",
    })
    g.add_conditional_edges("report", _route, {
        "continue": END,
        "retry": "report",
        "fail": "error",
    })
    g.add_edge("error", END)

    return g.compile()
