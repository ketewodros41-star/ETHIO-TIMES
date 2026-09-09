from __future__ import annotations

from app.core.config import settings
from app.services.social.editorial_engine import EditorialBrief

class CaptionBuilder:
    def build(self, brief: EditorialBrief) -> str:
        """Assemble Instagram caption from editorial brief."""
        parts = [
            brief.headline,
            brief.short_summary,
            brief.why_it_matters,
        ]
        
        if brief.key_facts:
            facts = "Key facts:\\n" + "\\n".join(f"• {f}" for f in brief.key_facts)
            parts.append(facts)
            
        parts.append(brief.source_attribution)
        parts.append(" ".join(brief.hashtags))
        
        caption = "\\n\\n".join(parts)
        if len(caption) > settings.caption_max_chars:
            # simplistic truncate
            caption = caption[:settings.caption_max_chars-3] + "..."
            
        return caption
