from langchain_core.messages import ToolMessage
import logging
import time
from state_graph import AgentState
from agents_prompt import assistant_prompt
from utils import parser,prepaer_states
import os
from tavily import TavilyClient

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')


# Step 1. Instantiating your TavilyClient
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

def scrapper(state: AgentState):
    question = state["query"]
    rid = state.get("correlation_id", "")
    t0 = time.time()

    logger.info("scrapper start rid=%s", rid)

    try:
        response = tavily_client.search(question)
        results = response.get("results") or []
    except Exception as exc:
        logger.warning(
            "scrapper failed rid=%s error_type=%s",
            rid, type(exc).__name__,
        )
        results = []

    if not results:
        logger.warning("scrapper no_results rid=%s", rid)
        return prepaer_states({
            "node": "scrapper",
            "context": "",
            "places": [],
            "call": "generator_agent",
        })

    context = str(results[0])

    logger.info(
        "scrapper complete rid=%s results=%d duration=%.2fs",
        rid, len(results), time.time() - t0,
    )
    return prepaer_states({
        "messages": [
            ToolMessage(
                content=context,
                name="scrapper",
                tool_call_id="call_scrapper",
            )
        ],
        "node": "scrapper",
        "context": context,
        "places": [],
        "call": "generator_agent",
    })