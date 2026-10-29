"""Answer verification (LLD section 9).

For now the verify node only stores the answer as the final text; the deterministic checks and the Sources list
are added with the renderer.
"""

from typing import Any

from research_agent.agent.nodes import VERIFY_NODE
from research_agent.agent.state import AgentState
from research_agent.log import NODE_KIND, log_call


@log_call(NODE_KIND, VERIFY_NODE)
async def verify_node(state: AgentState) -> dict[str, Any]:
    """Store the model's answer, with its content blocks joined as text, as the final answer."""
    answer = state["messages"][-1]
    return {"final": answer.text}
