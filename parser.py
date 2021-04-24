from dataclasses import dataclass
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass
class Book:
    symbol: str
    buy: list
    sell: list 

