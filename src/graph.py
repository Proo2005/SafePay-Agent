from langgraph.graph import StateGraph, END
from src.core.state import AgentState
from src.agents.doc_intelligence import DocumentIntelligenceAgent
from src.agents.verifier import ExtractionVerifier
from src.agents.matching import MatchingAgent
from src.agents.discrepancy import DiscrepancyDetectorAgent
from src.agents.resolution import ResolutionAgent
# 1. New Import for Fraud Check
from src.fraud_check import check_pdf_integrity

def extract_node(state: AgentState):
    """
    Step 1: Checks PDF for tampering (Photoshop, etc).
    Step 2: If clean, runs AI extraction.
    """
    # --- 🕵️ SECURITY LAYER START ---
    print("\n🕵️  --- SECURITY CHECK INITIATED ---")
    
    # We use .get() in case file_path isn't set yet
    file_path = state.get("file_path", "") 
    
    # Run the check
    is_suspicious, reason = check_pdf_integrity(file_path)
    
    if is_suspicious:
        print(f"🚨 FRAUD ALERT: {reason}")
        
        # Log the fraud detection in the trace so the final agent sees it
        state.agent_trace.append(
            {
                "agent": "Fraud Detector",
                "status": "Suspicious",
                "confidence": 1.0,
                "detail": f"⚠️ BLOCKED: {reason}",
            }
        )
        
        # Set the warning flag in the state
        state.fraud_warning = f"⚠️ SECURITY RISK: {reason}"
        
        # ⛔ STOP HERE. Do not send malicious files to the AI.
        # We return the state immediately. The next node (verify) will run, 
        # see empty data, and eventually the Resolution Agent will reject it.
        return state
        
    print(f"✅ Security Check Passed: {reason}")
    # --- SECURITY LAYER END ---

    # If safe, proceed with normal AI extraction
    agent = DocumentIntelligenceAgent()
    new_state = agent.process(state)

    new_state.agent_trace.append(
        {
            "agent": "Document Intelligence",
            "status": "Success",
            "confidence": new_state.extraction_confidence,
            "detail": f"Extracted {len(new_state.extracted_items)} line items. Notes: {new_state.extraction_reasoning}",
        }
    )
    return new_state


def verify_node(state: AgentState):
    # If we skipped extraction due to fraud, extracted_items will be empty.
    # We handle that gracefully.
    if state.fraud_warning:
        state.agent_trace.append({
            "agent": "Extraction Verifier",
            "status": "Skipped",
            "confidence": 1.0,
            "detail": "Skipped verification due to fraud alert."
        })
        return state

    agent = ExtractionVerifier()
    new_state = agent.verify(state)

    status = "Passed" if new_state.math_verification_passed else "Failed"
    detail = (
        "Math checks passed."
        if new_state.math_verification_passed
        else f"Found math errors: {new_state.verification_flags}"
    )

    new_state.agent_trace.append(
        {
            "agent": "Extraction Verifier",
            "status": status,
            "confidence": 1.0,
            "detail": detail,
        }
    )
    return new_state


def retry_node(state: AgentState):
    """
    Increments retry count and logs the loop.
    This must be a Node (not an edge) to persist the state change.
    """
    state.retry_count += 1
    state.agent_trace.append(
        {
            "agent": "Orchestrator",
            "status": "Looping",
            "confidence": 1.0,
            "detail": "Triggering re-extraction due to math verification failure.",
        }
    )
    return state


def match_node(state: AgentState):
    # Skip matching if fraud detected
    if state.fraud_warning:
        state.agent_trace.append({
            "agent": "Matching Agent",
            "status": "Skipped",
            "confidence": 1.0,
            "detail": "Skipped matching due to fraud alert."
        })
        return state

    agent = MatchingAgent(db_path="data/purchase_orders.json")
    new_state = agent.match(state)

    if new_state.matched_po_id:
        status = "Success"
        conf = (
            new_state.match_candidates[0].confidence
            if new_state.match_candidates
            else 0.0
        )
    else:
        status = "No Match"
        conf = 0.0

    new_state.agent_trace.append(
        {
            "agent": "Matching Agent",
            "status": status,
            "confidence": conf,
            "detail": new_state.match_reasoning,
        }
    )
    return new_state


def discrepancy_node(state: AgentState):
    # Skip checks if fraud detected
    if state.fraud_warning:
        return state

    agent = DiscrepancyDetectorAgent(db_path="data/purchase_orders.json")
    new_state = agent.check(state)

    count = len(new_state.discrepancies)
    detail = f"Found {count} discrepancies."
    if count > 0:
        types = [d.type for d in new_state.discrepancies]
        detail += f" Types: {', '.join(types)}"

    new_state.agent_trace.append(
        {
            "agent": "Discrepancy Detector",
            "status": "Flagged" if count > 0 else "Clean",
            "confidence": 1.0,  
            "detail": detail,
        }
    )
    return new_state


def resolution_node(state: AgentState):
    # If fraud was detected earlier, we force a rejection here.
    if state.fraud_warning:
        state.final_action = "REJECT"
        state.final_report_reasoning = f"⛔ SECURITY PROTOCOL: {state.fraud_warning}"
        state.agent_trace.append({
            "agent": "Resolution Agent",
            "status": "Complete",
            "confidence": 1.0,
            "detail": "Automatically Rejected due to Security Alert."
        })
        return state

    agent = ResolutionAgent()
    new_state = agent.resolve(state)

    new_state.agent_trace.append(
        {
            "agent": "Resolution Agent",
            "status": "Complete",
            "confidence": 1.0,
            "detail": f"Action: {new_state.final_action}. Reason: {new_state.final_report_reasoning}",
        }
    )
    return new_state


def should_retry_extraction(state: AgentState):
    """
    Decides if we should loop back.
    Checks state, returns string. Does NOT modify state.
    """
    # Don't retry if it's fraud
    if state.fraud_warning:
        return "continue"

    if not state.math_verification_passed and state.retry_count < 1:
        return "retry"
    return "continue"

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("extract", extract_node)
    builder.add_node("verify", verify_node)
    builder.add_node("retry_logic", retry_node)  
    builder.add_node("match", match_node)
    builder.add_node("discrepancy", discrepancy_node)
    builder.add_node("resolve", resolution_node)

    builder.set_entry_point("extract")

    builder.add_edge("extract", "verify")

    builder.add_conditional_edges(
        "verify",
        should_retry_extraction,
        {"retry": "retry_logic", "continue": "match"},  
    )

    builder.add_edge("retry_logic", "extract") 

    builder.add_edge("match", "discrepancy")
    builder.add_edge("discrepancy", "resolve")
    builder.add_edge("resolve", END)

    return builder.compile()