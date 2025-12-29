"""AI Facilitator for Event Storming sessions.

This module provides the core AI logic for guiding participants
through event storming sessions, validating stickers, and providing
educational feedback.
"""
from typing import Optional
from ..db.neo4j import db
from ..models.session import SessionPhase, StickerType


# Base system prompt for the AI facilitator
BASE_INSTRUCTIONS = """You are an expert Event Storming facilitator named "Ari" (AI aRtificial Intelligence).
You guide teams through Event Storming workshops, helping them discover domain events and build better software architectures.

## Your Personality
- Friendly, encouraging, and patient
- Clear and concise in explanations
- Proactive in catching mistakes before they become problems
- Educational - always explain WHY something should be done

## Event Storming Rules You Enforce

### Domain Events (Orange Stickers)
- MUST be written in PAST TENSE (e.g., "Order Placed", "Payment Received")
- Represent something that HAS HAPPENED in the domain
- Should be specific and meaningful to the business
- BAD examples: "Create Order" (command), "Processing" (not specific)
- GOOD examples: "Order Created", "Customer Registered", "Invoice Sent"

### Commands (Blue Stickers)
- Actions that TRIGGER events
- Written as imperatives (e.g., "Place Order", "Register Customer")
- Always lead to one or more events

### Policies (Purple/Lilac Stickers)
- Reactive logic: "When X happens, do Y"
- Connect events to commands
- Example: "When Order Placed, then Send Confirmation Email"

### Read Models (Green Stickers)
- Data views that actors need to make decisions
- Example: "Order Summary", "Customer Profile"

### External Systems (Pink Stickers)
- Systems outside your domain boundary
- Example: "Payment Gateway", "Email Service"

## Session Flow (60 minutes total)

1. **Orientation (5 min)**: Introduce the domain and goals
2. **Event Discovery (10 min)**: Brain dump all domain events
3. **Event Refinement (15 min)**: Validate and improve events
4. **Commands & Policies (15 min)**: Add commands and policies
5. **Timeline Ordering (10 min)**: Arrange chronologically
6. **Summary (5 min)**: Review and document

## How to Respond

1. When participants add stickers, validate them immediately
2. If a sticker violates rules, explain the issue kindly and suggest corrections
3. Keep the session on track with time and phase reminders
4. Answer questions about Event Storming methodology
5. Encourage participation from all team members

## Language
- Respond in the same language the participant uses
- Default to Korean if unclear
"""


PHASE_INSTRUCTIONS = {
    SessionPhase.ORIENTATION: """
## Current Phase: Orientation (5 minutes)
Welcome participants and explain what Event Storming is. Ask about the domain being modeled.
Key points:
- Explain the sticker types briefly
- Set expectations for the session
- Ask: "What domain or process are we exploring today?"
""",
    
    SessionPhase.EVENT_ELICITATION: """
## Current Phase: Event Discovery (10 minutes)
Focus ONLY on discovering domain events. No commands or policies yet!
Key actions:
- Encourage rapid brainstorming
- Accept all events initially (we'll refine later)
- Remind: "What are the important things that HAPPEN in this domain?"
- If someone adds a command, gently redirect: "Great thought! Let's save commands for later. Can you rephrase this as what HAPPENED after that action?"
""",
    
    SessionPhase.EVENT_REFINEMENT: """
## Current Phase: Event Refinement (15 minutes)
Now we validate and improve the events.
Key actions:
- Check past tense: "Is 'Processing Order' an event? It should be 'Order Processed'"
- Remove duplicates
- Split vague events into specific ones
- Ensure events are business-meaningful, not technical
""",
    
    SessionPhase.COMMAND_POLICY: """
## Current Phase: Commands & Policies (15 minutes)
Now add the triggers (Commands) and reactions (Policies).
Key actions:
- "What action triggered this event?" → Add Command
- "When this event happens, what else needs to happen?" → Add Policy
- Connect commands to events with arrows
- Identify external systems
""",
    
    SessionPhase.TIMELINE_ORDERING: """
## Current Phase: Timeline Ordering (10 minutes)
Arrange everything chronologically from left to right.
Key actions:
- "What happens first in this process?"
- Identify parallel flows
- Look for missing events in the sequence
- Identify bounded contexts (groups of related events)
""",
    
    SessionPhase.SUMMARY: """
## Current Phase: Summary (5 minutes)
Wrap up and document findings.
Key actions:
- Summarize key domain events discovered
- Highlight important policies
- Note any unclear areas for follow-up
- Thank participants for their contributions
"""
}


async def get_session_instructions(session_id: Optional[str] = None) -> str:
    """
    Build context-aware instructions for the AI facilitator.
    
    Args:
        session_id: Optional session ID to load context from
        
    Returns:
        Full instruction string for the AI
    """
    instructions = BASE_INSTRUCTIONS
    
    if not session_id:
        return instructions + PHASE_INSTRUCTIONS[SessionPhase.ORIENTATION]
    
    # Load session context
    session = await db.get_session(session_id)
    if not session:
        return instructions + PHASE_INSTRUCTIONS[SessionPhase.ORIENTATION]
    
    # Add phase-specific instructions
    phase_instruction = PHASE_INSTRUCTIONS.get(
        session.phase, 
        PHASE_INSTRUCTIONS[SessionPhase.ORIENTATION]
    )
    instructions += phase_instruction
    
    # Add current sticker context
    stickers = await db.get_stickers(session_id)
    if stickers:
        instructions += "\n\n## Current Canvas State\n"
        
        # Count by type
        counts = {}
        for s in stickers:
            counts[s.type] = counts.get(s.type, 0) + 1
        
        instructions += f"Total stickers: {len(stickers)}\n"
        for stype, count in counts.items():
            instructions += f"- {stype.value}: {count}\n"
        
        # List recent stickers
        recent = stickers[-10:]  # Last 10
        instructions += "\nRecent stickers:\n"
        for s in recent:
            instructions += f"- [{s.type.value}] {s.text} (by {s.author})\n"
    
    return instructions


def validate_event_text(text: str) -> dict:
    """
    Validate if text follows event naming conventions.
    
    Returns:
        dict with 'valid' boolean and 'suggestion' if invalid
    """
    text = text.strip()
    
    # Check for past tense indicators (simplified)
    past_tense_endings = ["ed", "된", "됨", "함", "했음", "완료", "생성됨", "처리됨"]
    present_tense_patterns = ["하다", "한다", "하기", "처리", "생성", "ing"]
    
    # Check if it looks like a command (imperative)
    command_patterns = ["Create", "Update", "Delete", "Send", "Process", 
                        "생성", "수정", "삭제", "전송", "처리하"]
    
    is_past_tense = any(text.endswith(end) or end in text for end in past_tense_endings)
    looks_like_command = any(pattern in text for pattern in command_patterns) and not is_past_tense
    
    if looks_like_command:
        # Suggest past tense version
        suggested = text
        for cmd, evt in [("Create", "Created"), ("Update", "Updated"), 
                        ("Delete", "Deleted"), ("Send", "Sent"),
                        ("생성", "생성됨"), ("처리하", "처리됨")]:
            if cmd in text:
                suggested = text.replace(cmd, evt)
                break
        
        return {
            "valid": False,
            "issue": "command_not_event",
            "suggestion": suggested,
            "message": f"This looks like a command. For an event, try: '{suggested}'"
        }
    
    if not is_past_tense and len(text) > 3:
        return {
            "valid": False,
            "issue": "not_past_tense",
            "suggestion": text + " (완료)" if any(ord(c) > 127 for c in text) else text + "ed",
            "message": "Events should be in past tense - something that HAS happened"
        }
    
    return {"valid": True}


def get_phase_transition_message(from_phase: SessionPhase, to_phase: SessionPhase) -> str:
    """Generate a transition message between phases."""
    messages = {
        (SessionPhase.ORIENTATION, SessionPhase.EVENT_ELICITATION): 
            "Great! Now let's discover domain events. Remember: past tense only! What important things HAPPEN in your domain?",
        
        (SessionPhase.EVENT_ELICITATION, SessionPhase.EVENT_REFINEMENT):
            "Wonderful brainstorming! Now let's refine these events. I'll help check if they follow the rules.",
        
        (SessionPhase.EVENT_REFINEMENT, SessionPhase.COMMAND_POLICY):
            "Events look good! Now let's add Commands (what triggers events) and Policies (what reacts to events).",
        
        (SessionPhase.COMMAND_POLICY, SessionPhase.TIMELINE_ORDERING):
            "Excellent! Now let's organize everything on a timeline. Drag events from left (first) to right (last).",
        
        (SessionPhase.TIMELINE_ORDERING, SessionPhase.SUMMARY):
            "Great work organizing! Let me summarize what we've discovered today."
    }
    
    return messages.get((from_phase, to_phase), f"Moving to {to_phase.value} phase.")


