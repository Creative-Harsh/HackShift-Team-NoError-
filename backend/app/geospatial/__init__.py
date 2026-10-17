"""Mongo-compatible GeoJSON distances. No mock replacement for production queries."""
from math import asin, cos, radians, sin, sqrt


def haversine_km(a, b):
    lon1, lat1 = map(radians, a)
    lon2, lat2 = map(radians, b)
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * asin(min(1.0, sqrt(max(0.0, value))))


def nearby_query(longitude, latitude, radius_km, since, query=None, until=None):
    from app.database import utcnow
    return {**(query or {}), 'reported_at': {'$gte': since, '$lte': until or utcnow()}, 'location': {'$near': {
        '$geometry': {'type': 'Point', 'coordinates': [longitude, latitude]},
        '$maxDistance': radius_km * 1000}}}
