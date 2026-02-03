
from pydantic import BaseModel, Field
import operator
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Union
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # The list of chat messages (Human, AI, Tool)
    messages: Annotated[list, add_messages]
    
    # --- File & Security Tracking ---
    file_path: str
    fraud_warning: Optional[str]
    
    # --- Extraction Data ---
    extracted_items: List[Dict[str, Any]]  # This was causing your error!
    extraction_confidence: float
    extraction_reasoning: str
    
    # --- Verification Data ---
    math_verification_passed: bool
    verification_flags: List[str]
    retry_count: int
    
    # --- Matching Data ---
    matched_po_id: Optional[str]
    match_candidates: List[Any]
    match_reasoning: str
    
    # --- Discrepancy Data ---
    discrepancies: List[Any]
    
    # --- Final Resolution ---
    final_action: str
    final_report_reasoning: str
    
    # --- Audit Trail ---
    agent_trace: List[Dict[str, Any]]

class ExtractedLineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    line_total: float
    confidence: float


class Discrepancy(BaseModel):
    type: str
    severity: str
    field: str
    details: str
    invoice_value: Optional[Any]
    po_value: Optional[Any]
    confidence: float


class POMatchCandidate(BaseModel):
    po_number: str
    confidence: float
    method: str
    reasoning: str

