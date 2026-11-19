from state_graph import AgentState

def assitant_router(state: AgentState):
    return state["call"]

def scrapper_router(state: AgentState):
    return state.get("call", "generator_agent")

def reviewer_router(state: AgentState):
    return state["call"]


def IoT_router(state: AgentState):
    return state["call"]

def googlemaps_router(state: AgentState):
    return state["call"]

def generator_router(state: AgentState):
    target = state.get("call", "reviewer_agent")
    allowed = {
        "GoogleMaps",
        "scrapper",
        "reviewer_agent",
        "finalize_turn",
    }
    if target not in allowed:
        raise ValueError(f"Unexpected generator route: {target}")
    return target
