from typing import Dict, List

from aeromcp.capabilities.prompts.base import BasePrompt
from aeromcp.types.common import SpecType


class PromptRegistry:
    def __init__(self) -> None:
        self._prompts: Dict[str, BasePrompt] = {}

    def register(self, prompt: BasePrompt) -> None:
        if prompt.name in self._prompts:
            raise ValueError(f"Prompt '{prompt.name}' already registered")

        self._prompts[prompt.name] = prompt

    def get(self, name: str) -> BasePrompt:
        try:
            return self._prompts[name]
        except KeyError:
            raise ValueError(f"Prompt '{name}' not found")

    def list(self) -> List[SpecType]:
        return [prompt.spec for prompt in self._prompts.values()]
