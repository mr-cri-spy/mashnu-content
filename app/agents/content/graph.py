"""LangGraph flow: extract insight -> draft per platform -> critique -> (retry once) -> done."""
import re
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.content.llm import LLM, get_llm
from app.agents.content.prompts.platforms import PLATFORM_RULES

VOICE = (Path(__file__).parent / "prompts" / "voice.md").read_text()
MIN_SCORE = 7
MAX_RETRIES = 1


class State(TypedDict, total=False):
    note: str
    platforms: list[str]
    insight: str
    drafts: dict[str, str]
    scores: dict[str, int]
    feedback: dict[str, str]
    retries: int


def build_graph(llm: LLM | None = None):
    llm = llm or get_llm()

    def extract(state: State) -> State:
        insight = llm.complete(
            "INSIGHT extractor. From the founder note, return the single most specific, "
            "non-obvious lesson in 2 sentences. Keep every number and tool name.",
            state["note"],
        )
        return {"insight": insight, "retries": 0}

    def draft(state: State) -> State:
        drafts = dict(state.get("drafts", {}))
        for p in state["platforms"]:
            # only redraft platforms that failed critique (or all on first pass)
            if p in drafts and state.get("scores", {}).get(p, 0) >= MIN_SCORE:
                continue
            fb = state.get("feedback", {}).get(p, "")
            drafts[p] = llm.complete(
                VOICE + "\n\nFORMAT: " + PLATFORM_RULES[p],
                f"SOURCE NOTE:\n{state['note']}\n\nKEY INSIGHT:\n{state['insight']}\n"
                + (f"\nFIX THESE ISSUES FROM LAST DRAFT:\n{fb}" if fb else ""),
            )
        return {"drafts": drafts}

    def critique(state: State) -> State:
        scores, feedback = {}, {}
        for p, text in state["drafts"].items():
            out = llm.complete(
                "SCORE the draft 1-10. Penalize: generic claims, hype words, invented facts, "
                "no concrete specific, wrong format. Reply exactly:\nSCORE: <n>\nFEEDBACK: <one line>",
                f"FORMAT: {PLATFORM_RULES[p]}\nSOURCE NOTE:\n{state['note']}\n\nDRAFT:\n{text}",
            )
            m = re.search(r"SCORE:\s*(\d+)", out)
            scores[p] = int(m.group(1)) if m else 0
            f = re.search(r"FEEDBACK:\s*(.*)", out)
            feedback[p] = f.group(1).strip() if f else ""
        return {"scores": scores, "feedback": feedback, "retries": state.get("retries", 0) + 1}

    def route(state: State) -> str:
        weak = any(s < MIN_SCORE for s in state["scores"].values())
        return "draft" if weak and state["retries"] <= MAX_RETRIES else END

    g = StateGraph(State)
    g.add_node("extract", extract)
    g.add_node("draft", draft)
    g.add_node("critique", critique)
    g.set_entry_point("extract")
    g.add_edge("extract", "draft")
    g.add_edge("draft", "critique")
    g.add_conditional_edges("critique", route, {"draft": "draft", END: END})
    return g.compile()
