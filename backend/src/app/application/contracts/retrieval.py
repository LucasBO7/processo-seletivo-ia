from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Startup


@dataclass(frozen=True, slots=True)
class TeamSizeRange:
    minimum: int
    maximum: int | None = None

    def __post_init__(self) -> None:
        if self.minimum < 0 or (self.maximum is not None and self.maximum < self.minimum):
            raise ValueError("invalid team size range")


@dataclass(frozen=True, slots=True)
class StartupSearchCriteria:
    sectors: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()
    team_size_ranges: tuple[TeamSizeRange, ...] = ()
    requires_team_size_match: bool = False

    @property
    def structured_filter_count(self) -> int:
        return sum(
            bool(value)
            for value in (
                self.sectors,
                self.stages,
                self.locations,
                self.team_size_ranges,
            )
        )


@dataclass(frozen=True, slots=True)
class RankedStartup:
    startup: Startup
    score: float
