



import json
from typing import Any, List


def extract_text_from_content(content: Any) -> str:
    """Normalize Gemini content payloads into a plain text string."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if "text" in block and isinstance(block["text"], str):
                    chunks.append(block["text"])
                elif "value" in block and isinstance(block["value"], str):
                    chunks.append(block["value"])
                elif "content" in block and isinstance(block["content"], str):
                    chunks.append(block["content"])
            elif isinstance(block, str):
                chunks.append(block)
        return "".join(chunks)

    if isinstance(content, dict):
        for key in ("text", "value", "content"):
            if isinstance(content.get(key), str):
                return content[key]
        return json.dumps(content, ensure_ascii=False)

    return str(content)


def print_clean_debug(step_name, message_object):
    """Affiche le contenu du LLM proprement en virant la signature Google."""
    content = message_object.content
    
    print(f"\n--- DEBUG {step_name} ---")
    print(f" CONTENU : {extract_text_from_content(content)}")
    
    if hasattr(message_object, 'tool_calls') and message_object.tool_calls:
        for tool in message_object.tool_calls:
            print(f" APPEL OUTIL : {tool['name']} avec args={tool['args']}")

    print("-" * 30)