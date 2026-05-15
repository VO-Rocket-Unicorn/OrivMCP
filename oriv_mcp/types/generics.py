from typing import TypeVar

from pydantic import BaseModel


T_Input = TypeVar("T_Input", bound=BaseModel)
T_Output = TypeVar("T_Output", bound=BaseModel)
