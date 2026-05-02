from dataclasses import dataclass
from datetime import datetime
from typing import List
from rich import print


@dataclass
class MatchCandidate():
    candidate_name: str
    candidate_date: datetime
    candidate_score: float

    def __str__(self):
        date = self.candidate_date.strftime('%d/%m/%y')
        if self.candidate_score >= 98:
            color = "green1"
        elif self.candidate_score >= 90:
            color = "bright_green"
        elif self.candidate_score >= 85:
            color = "orange3"
        else:
            color = "bright_red"
    
        return f"[{color}]{int(self.candidate_score)}% {self.candidate_name} {date}  [/]"

@dataclass
class MultiMatchResult():
    target_name: str
    candidates: List['MatchCandidate'] # Assuming MatchCandidate is defined elsewhere

    # def __str__(self):
    #     # This determines exactly what print(result) outputs
    #     output = [f"Target: [red]{self.targe_name}[/]\n"]
        
    #     for cand in self.finalcandidates:
    #         output.append(f"  -> {cand.candidate_name} {int(cand.candidate_score)}% ")
            
    #     return "\n".join(output)

