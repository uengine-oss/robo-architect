from __future__ import annotations

from typing import Optional


def extract_section(text: str, section_name: str) -> Optional[str]:
    import re

    patterns = [
        # Supports emoji-prefixed sections (💭/⚡/👁️/✅) and multi-line content.
        # Stop at the next section header, a JSON fence, or end of text.
        rf"(?:💭|⚡|👁️|✅)?\s*{section_name}:\s*(.+?)(?=(?:💭|⚡|👁️|✅)?\s*(?:THOUGHT|ACTION|OBSERVATION|SUMMARY)|```|$)",
        rf"{section_name}:\s*(.+?)(?=\n|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


