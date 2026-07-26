"""
Geo-information platform — aggregates geographic data from multiple sources.
"""
from geo.aggregator import GeoDataAggregator
from geo.models import GeoResult, Location
from geo.provider import GeoDataProvider

__all__ = ["GeoDataProvider", "GeoDataAggregator", "GeoResult", "Location"]
