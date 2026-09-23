"""Official QalaAI scenario data; no simulation calculations."""

SIMULATION_HORIZON = 8
BUDGET = 100
REQUIRED_DECISIONS = 5

INDICATOR_WEIGHTS = {
    "T1": 0.10,
    "T2": 0.10,
    "E1": 0.09,
    "E2": 0.11,
    "S1": 0.11,
    "S2": 0.11,
    "B1": 0.09,
    "B2": 0.09,
    "C1": 0.10,
    "C2": 0.10,
}

INDICATOR_METADATA = {
    "T1": "Road congestion relief",
    "T2": "Public transport accessibility",
    "E1": "Green space",
    "E2": "Air quality",
    "S1": "Schools and kindergartens",
    "S2": "Clinics and primary healthcare",
    "B1": "Street safety",
    "B2": "Road safety",
    "C1": "Utility reliability",
    "C2": "Citizen request resolution speed",
}

DISTRICTS = {
    "Esil": {
        "population_share": 0.27,
        "indicators": {
            "T1": 45, "T2": 62, "E1": 68, "E2": 72, "S1": 48,
            "S2": 55, "B1": 78, "B2": 60, "C1": 75, "C2": 70,
        },
    },
    "Almaty": {
        "population_share": 0.24,
        "indicators": {
            "T1": 40, "T2": 75, "E1": 50, "E2": 55, "S1": 60,
            "S2": 65, "B1": 62, "B2": 52, "C1": 50, "C2": 60,
        },
    },
    "Saryarka": {
        "population_share": 0.20,
        "indicators": {
            "T1": 50, "T2": 70, "E1": 42, "E2": 40, "S1": 62,
            "S2": 68, "B1": 58, "B2": 55, "C1": 45, "C2": 55,
        },
    },
    "Baikonur": {
        "population_share": 0.13,
        "indicators": {
            "T1": 52, "T2": 68, "E1": 55, "E2": 50, "S1": 58,
            "S2": 60, "B1": 52, "B2": 58, "C1": 55, "C2": 58,
        },
    },
    "Nura": {
        "population_share": 0.16,
        "indicators": {
            "T1": 55, "T2": 40, "E1": 45, "E2": 65, "S1": 38,
            "S2": 35, "B1": 55, "B2": 50, "C1": 60, "C2": 50,
        },
    },
}

MEASURES = {
    "M1": {
        "category": "Transport",
        "name": "Dedicated bus lanes",
        "type": "district",
        "cost": 18,
        "lag": 2,
        "effects": {"T1": 6, "T2": 9},
    },
    "M2": {
        "category": "Transport",
        "name": "Smart traffic lights",
        "type": "city",
        "cost": 22,
        "lag": 2,
        "effects": {"T1": 4, "B2": 3},
    },
    "M3": {
        "category": "Transport",
        "name": "LRT line / expansion",
        "type": "district",
        "cost": 30,
        "lag": 4,
        "effects": {"T1": 16, "T2": 20, "E2": 4},
    },
    "M4": {
        "category": "Environment",
        "name": "Park / public garden",
        "type": "district",
        "cost": 15,
        "lag": 2,
        "effects": {"E1": 12, "E2": 3, "B1": 2},
    },
    "M5": {
        "category": "Environment",
        "name": "Clean fuel transition for private sector",
        "type": "district",
        "cost": 25,
        "lag": 3,
        "effects": {"E2": 14, "C1": 4},
    },
    "M6": {
        "category": "Environment",
        "name": "City greening and windbreak program",
        "type": "city",
        "cost": 20,
        "lag": 4,
        "effects": {"E1": 5, "E2": 3},
    },
    "M7": {
        "category": "Social",
        "name": "School + kindergarten",
        "type": "district",
        "cost": 24,
        "lag": 3,
        "effects": {"S1": 16},
    },
    "M8": {
        "category": "Social",
        "name": "Family health center / clinic",
        "type": "district",
        "cost": 20,
        "lag": 3,
        "effects": {"S2": 14},
    },
    "M9": {
        "category": "Social",
        "name": "Neighborhood sports hubs",
        "type": "district",
        "cost": 10,
        "lag": 1,
        "effects": {"S1": 3, "S2": 3, "B1": 3},
    },
    "M10": {
        "category": "Safety",
        "name": "Lighting and cameras / Safe City",
        "type": "district",
        "cost": 12,
        "lag": 1,
        "effects": {"B1": 12, "B2": 2},
    },
    "M11": {
        "category": "Safety",
        "name": "Safe crossings and school zones",
        "type": "district",
        "cost": 10,
        "lag": 1,
        "effects": {"B2": 12, "T1": -2},
    },
    "M12": {
        "category": "Services",
        "name": "Unified digital citizen request platform",
        "type": "city",
        "cost": 14,
        "lag": 1,
        "effects": {"C2": 5},
    },
    "M13": {
        "category": "Services",
        "name": "Heating and water network modernization",
        "type": "district",
        "cost": 28,
        "lag": 4,
        "effects": {"C1": 18, "E2": 2},
    },
    "M14": {
        "category": "Services",
        "name": "Emergency utility teams + early warning",
        "type": "city",
        "cost": 16,
        "lag": 1,
        "effects": {"C1": 5, "C2": 2},
    },
}

# Bonuses apply in the district selected for district_measure.
# They are fixed and are NOT scaled by lag.
SYNERGIES = [
    {
        "measures": ["M1", "M2"],
        "district_measure": "M1",
        "effects": {"T1": 2},
        "scale_by_lag": False,
    },
    {
        "measures": ["M10", "M12"],
        "district_measure": "M10",
        "effects": {"B1": 2},
        "scale_by_lag": False,
    },
    {
        "measures": ["M5", "M6"],
        "district_measure": "M5",
        "effects": {"E2": 2},
        "scale_by_lag": False,
    },
]

# Global incompatibility applies regardless of district; same_district
# incompatibility applies only when both measures target the same district.
INCOMPATIBILITIES = [
    {"measures": ["M1", "M3"], "scope": "global"},
    {"measures": ["M4", "M7"], "scope": "same_district"},
    {"measures": ["M5", "M13"], "scope": "same_district"},
]
