"""
Processing layers package.
All layers use the BaseLayer contract from base.py.
"""
from .syntax import SyntaxLayer
from .spam_filter import SpamFilterLayer
from .infra import InfraLayer
from .catchall import CatchallLayer
from .bounce_score import BounceScoreLayer
from .domain_age import DomainAgeLayer
from .spam_copy import SpamCopyLayer
from .burn_score import BurnScoreLayer
from .domain_blacklist import DomainBlacklistLayer

__all__ = [
    "SyntaxLayer",
    "SpamFilterLayer",
    "InfraLayer",
    "CatchallLayer",
    "BounceScoreLayer",
    "DomainAgeLayer",
    "SpamCopyLayer",
    "BurnScoreLayer",
    "DomainBlacklistLayer",
]
