"""Market data for French real estate.

This module contains:
- Market prices (rental and sale) per m² for Île-de-France cities
- City profiles with safety, transport, growth, and quality ratings
- Grand Paris Express and Olympic impact flags
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class SafetyLevel(int, Enum):
    """Safety rating for neighborhoods (1-5 scale)."""

    VERY_LOW = 1  # Challenging areas
    LOW = 2  # Below average safety
    MEDIUM = 3  # Average
    HIGH = 4  # Above average
    VERY_HIGH = 5  # Very safe, premium areas


class TransportLevel(int, Enum):
    """Public transport accessibility (1-5 scale)."""

    VERY_LOW = 1  # Poor connectivity
    LOW = 2  # Limited options
    MEDIUM = 3  # Reasonable access
    HIGH = 4  # Good metro/RER
    VERY_HIGH = 5  # Excellent, multiple lines


class GrowthPotential(int, Enum):
    """Expected price/value growth potential (1-5 scale)."""

    VERY_LOW = 1  # Declining or stagnant
    LOW = 2  # Limited growth
    MEDIUM = 3  # Steady growth
    HIGH = 4  # Good appreciation expected
    VERY_HIGH = 5  # Major development, strong growth


@dataclass
class MarketData:
    """Market price data for a location."""

    location_name: str
    rental_price_m2: float  # €/m²/month for unfurnished
    sale_price_m2: float  # €/m² purchase price

    # Optional details
    rental_furnished_premium: float = 0.30  # Premium for furnished (30%)
    rental_supply: Optional[int] = None  # Properties on rental market
    sale_supply: Optional[int] = None  # Properties on sale market

    # Calculated fields
    @property
    def gross_yield(self) -> float:
        """Calculate gross rental yield (unfurnished)."""
        return (self.rental_price_m2 * 12 / self.sale_price_m2) * 100

    @property
    def furnished_rental_m2(self) -> float:
        """Estimate furnished rental price per m²."""
        return self.rental_price_m2 * (1 + self.rental_furnished_premium)

    @property
    def furnished_gross_yield(self) -> float:
        """Calculate gross yield for furnished rental."""
        return (self.furnished_rental_m2 * 12 / self.sale_price_m2) * 100

    def estimate_rent(self, surface: float, furnished: bool = False) -> float:
        """Estimate monthly rent for a property."""
        price_m2 = self.furnished_rental_m2 if furnished else self.rental_price_m2
        return price_m2 * surface

    def estimate_value(self, surface: float) -> float:
        """Estimate property value based on surface."""
        return self.sale_price_m2 * surface


@dataclass
class CityProfile:
    """Complete profile for a city/neighborhood."""

    name: str
    department: str  # "75", "92", "93", "94", "95", "91", etc.

    # Ratings (1-5 scale)
    safety: int = 3
    transport: int = 3
    growth: int = 3
    quality: int = 3  # Quality of life
    amenities: int = 3  # Shops, restaurants, services

    # Special flags
    grand_paris: bool = False  # Grand Paris Express station nearby
    olympic: bool = False  # Olympic development impact
    renewal: bool = False  # Urban renewal project

    # Socio-economic
    median_income: Optional[int] = None  # €/year
    unemployment_rate: Optional[float] = None  # %

    # Notes
    notes: str = ""

    # Market data (linked)
    market_data: Optional[MarketData] = None

    @property
    def overall_score(self) -> float:
        """Calculate overall location score (0-5)."""
        base_score = (
            self.safety * 0.25
            + self.transport * 0.25
            + self.growth * 0.20
            + self.quality * 0.15
            + self.amenities * 0.15
        )

        # Bonuses
        if self.grand_paris:
            base_score += 0.2
        if self.olympic:
            base_score += 0.1
        if self.renewal:
            base_score += 0.05

        return min(base_score, 5.0)

    @property
    def investment_score(self) -> float:
        """Calculate investment attractiveness score."""
        # Weight growth and yield more for investment
        if not self.market_data:
            return self.overall_score

        yield_score = min(self.market_data.gross_yield / 2, 5)  # 10% yield = 5 score

        return (
            yield_score * 0.35
            + self.safety * 0.15
            + self.transport * 0.15
            + self.growth * 0.20
            + self.quality * 0.10
            + self.amenities * 0.05
            + (0.15 if self.grand_paris else 0)
            + (0.10 if self.olympic else 0)
        )

    def get_grade(self) -> str:
        """Get letter grade for investment potential."""
        score = self.investment_score
        if score >= 4.0:
            return "A+"
        elif score >= 3.5:
            return "A"
        elif score >= 3.0:
            return "B+"
        elif score >= 2.5:
            return "B"
        elif score >= 2.0:
            return "C"
        else:
            return "D"


# =============================================================================
# ILE-DE-FRANCE MARKET DATA (from SeLoger analysis)
# Source: seloger_market_analysis.csv
# =============================================================================

IDF_MARKET_DATA: Dict[str, MarketData] = {
    # PARIS
    "Paris 1Er": MarketData("Paris 1Er", 37, 12336),
    "Paris 2Eme": MarketData("Paris 2Eme", 37, 11120),
    "Paris 3Eme": MarketData("Paris 3Eme", 37, 11917),
    "Paris 4Eme": MarketData("Paris 4Eme", 37, 12528),
    "Paris 5Eme": MarketData("Paris 5Eme", 35, 11857),
    "Paris 6Eme": MarketData("Paris 6Eme", 38, 15438),
    "Paris 7Eme": MarketData("Paris 7Eme", 38, 14823),
    "Paris 8Eme": MarketData("Paris 8Eme", 36, 12465),
    "Paris 9Eme": MarketData("Paris 9Eme", 35, 10593),
    "Paris 10Eme": MarketData("Paris 10Eme", 33, 9444),
    "Paris 11Eme": MarketData("Paris 11Eme", 33, 10078),
    "Paris 12Eme": MarketData("Paris 12Eme", 31, 9204),
    "Paris 13Eme": MarketData("Paris 13Eme", 30, 8677),
    "Paris 14Eme": MarketData("Paris 14Eme", 32, 9581),
    "Paris 15Eme": MarketData("Paris 15Eme", 32, 9444),
    "Paris 16Eme": MarketData("Paris 16Eme", 35, 11196),
    "Paris 17Eme": MarketData("Paris 17Eme", 34, 10215),
    "Paris 18Eme": MarketData("Paris 18Eme", 31, 9186),
    "Paris 19Eme": MarketData("Paris 19Eme", 29, 8205),
    "Paris 20Eme": MarketData("Paris 20Eme", 30, 8356),
    # SEINE-SAINT-DENIS (93) - Higher yields
    "Saint Denis": MarketData("Saint Denis", 20, 3628),
    "Saint Ouen": MarketData("Saint Ouen", 24, 6193),
    "Aubervilliers": MarketData("Aubervilliers", 21, 3527),
    "Pantin": MarketData("Pantin", 23, 6218),
    "Montreuil": MarketData("Montreuil", 24, 6578),
    "Le Pre Saint Gervais": MarketData("Le Pre Saint Gervais", 24, 6172),
    "Les Lilas": MarketData("Les Lilas", 24, 6701),
    "Bagnolet": MarketData("Bagnolet", 24, 5836),
    "Romainville": MarketData("Romainville", 20, 5416),
    "Noisy Le Sec": MarketData("Noisy Le Sec", 19, 3496),
    "Bondy": MarketData("Bondy", 18, 2844),
    "Bobigny": MarketData("Bobigny", 19, 3100),
    "Drancy": MarketData("Drancy", 20, 3173),
    "Le Bourget": MarketData("Le Bourget", 19, 3340),
    "La Courneuve": MarketData("La Courneuve", 19, 3147),
    "Stains": MarketData("Stains", 18, 2472),
    "Pierrefitte Sur Seine": MarketData("Pierrefitte Sur Seine", 18, 2745),
    "Villetaneuse": MarketData("Villetaneuse", 19, 2736),
    "Epinay Sur Seine": MarketData("Epinay Sur Seine", 19, 2771),
    # HAUTS-DE-SEINE (92) - Premium suburbs
    "Boulogne Billancourt": MarketData("Boulogne Billancourt", 29, 8219),
    "Issy Les Moulineaux": MarketData("Issy Les Moulineaux", 27, 7438),
    "Levallois Perret": MarketData("Levallois Perret", 31, 8815),
    "Neuilly Sur Seine": MarketData("Neuilly Sur Seine", 33, 10533),
    "Clichy": MarketData("Clichy", 28, 6946),
    "Asnieres Sur Seine": MarketData("Asnieres Sur Seine", 24, 6191),
    "Courbevoie": MarketData("Courbevoie", 25, 6660),
    "Puteaux": MarketData("Puteaux", 27, 7233),
    "Nanterre": MarketData("Nanterre", 24, 5347),
    "Gennevilliers": MarketData("Gennevilliers", 20, 4687),
    "Colombes": MarketData("Colombes", 24, 5351),
    "Rueil Malmaison": MarketData("Rueil Malmaison", 25, 5616),
    "Suresnes": MarketData("Suresnes", 26, 6781),
    "Montrouge": MarketData("Montrouge", 26, 7082),
    "Malakoff": MarketData("Malakoff", 26, 6757),
    "Vanves": MarketData("Vanves", 26, 6333),
    "Clamart": MarketData("Clamart", 24, 5674),
    "Meudon": MarketData("Meudon", 23, 5755),
    "Chatillon": MarketData("Chatillon", 23, 5807),
    "Bagneux": MarketData("Bagneux", 22, 5238),
    "Fontenay Aux Roses": MarketData("Fontenay Aux Roses", 22, 4500),
    "Chatenay Malabry": MarketData("Chatenay Malabry", 22, 4454),
    "Sceaux": MarketData("Sceaux", 23, 5849),
    "Antony": MarketData("Antony", 22, 4924),
    "Bourg La Reine": MarketData("Bourg La Reine", 23, 5376),
    "Le Plessis Robinson": MarketData("Le Plessis Robinson", 22, 5539),
    "Saint Cloud": MarketData("Saint Cloud", 26, 6541),
    "Garches": MarketData("Garches", 25, 5683),
    "Sevres": MarketData("Sevres", 25, 5542),
    "Chaville": MarketData("Chaville", 23, 5087),
    "Villeneuve La Garenne": MarketData("Villeneuve La Garenne", 19, 3354),
    "Bois Colombes": MarketData("Bois Colombes", 24, 5967),
    "La Garenne Colombes": MarketData("La Garenne Colombes", 24, 6138),
    # VAL-DE-MARNE (94)
    "Vincennes": MarketData("Vincennes", 28, 8751),
    "Saint Mande": MarketData("Saint Mande", 30, 9661),
    "Charenton Le Pont": MarketData("Charenton Le Pont", 26, 7609),
    "Saint Maurice": MarketData("Saint Maurice", 25, 6396),
    "Ivry Sur Seine": MarketData("Ivry Sur Seine", 24, 5065),
    "Villejuif": MarketData("Villejuif", 23, 4896),
    "Vitry Sur Seine": MarketData("Vitry Sur Seine", 20, 4235),
    "Creteil": MarketData("Creteil", 20, 3863),
    "Maisons Alfort": MarketData("Maisons Alfort", 22, 5404),
    "Alfortville": MarketData("Alfortville", 22, 5264),
    "Cachan": MarketData("Cachan", 22, 5290),
    "Gentilly": MarketData("Gentilly", 24, 6115),
    "Le Kremlin Bicetre": MarketData("Le Kremlin Bicetre", 24, 5726),
    "Nogent Sur Marne": MarketData("Nogent Sur Marne", 24, 6188),
    "Le Perreux Sur Marne": MarketData("Le Perreux Sur Marne", 24, 5596),
    "Fontenay Sous Bois": MarketData("Fontenay Sous Bois", 24, 5962),
    "Joinville Le Pont": MarketData("Joinville Le Pont", 24, 5824),
    "Champigny Sur Marne": MarketData("Champigny Sur Marne", 20, 3972),
    "Arcueil": MarketData("Arcueil", 23, 5527),
    # VAL-D'OISE (95)
    "Argenteuil": MarketData("Argenteuil", 19, 3346),
    "Sarcelles": MarketData("Sarcelles", 18, 2409),
    "Cergy": MarketData("Cergy", 18, 3105),
    "Pontoise": MarketData("Pontoise", 18, 3272),
    "Enghien Les Bains": MarketData("Enghien Les Bains", 21, 5206),
    "Montmorency": MarketData("Montmorency", 20, 4055),
    "Eaubonne": MarketData("Eaubonne", 20, 3371),
    "Garges Les Gonesse": MarketData("Garges Les Gonesse", 18, 2569),
    "Bezons": MarketData("Bezons", 20, 4209),
    "Herblay": MarketData("Herblay", 22, 3923),
    "Saint Gratien": MarketData("Saint Gratien", 20, 3636),
    "Deuil La Barre": MarketData("Deuil La Barre", 20, 3473),
    "Ermont": MarketData("Ermont", 19, 3507),
    "Taverny": MarketData("Taverny", 18, 3491),
    "Soisy Sous Montmorency": MarketData("Soisy Sous Montmorency", 20, 3642),
    "Saint Leu La Foret": MarketData("Saint Leu La Foret", 20, 3625),
    "Cormeilles En Parisis": MarketData("Cormeilles En Parisis", 21, 4104),
    "Sartrouville": MarketData("Sartrouville", 22, 3923),
    "Goussainville": MarketData("Goussainville", 17, 2851),
    # ESSONNE (91)
    "Grigny": MarketData("Grigny", 15, 1489),
    "Ris Orangis": MarketData("Ris Orangis", 17, 2041),
    "Evry Courcouronnes": MarketData("Evry Courcouronnes", 16, 2351),
    "Corbeil Essonnes": MarketData("Corbeil Essonnes", 16, 2356),
    "Massy": MarketData("Massy", 20, 3958),
    "Palaiseau": MarketData("Palaiseau", 19, 4024),
    "Longjumeau": MarketData("Longjumeau", 17, 2969),
    "Savigny Sur Orge": MarketData("Savigny Sur Orge", 18, 3220),
    "Juvisy Sur Orge": MarketData("Juvisy Sur Orge", 18, 3423),
    "Athis Mons": MarketData("Athis Mons", 18, 3249),
    "Viry Chatillon": MarketData("Viry Chatillon", 17, 2873),
    "Draveil": MarketData("Draveil", 18, 3181),
    "Brunoy": MarketData("Brunoy", 18, 3380),
    "Yerres": MarketData("Yerres", 19, 3424),
    "Montgeron": MarketData("Montgeron", 18, 3756),
    "Sainte Genevieve Des Bois": MarketData("Sainte Genevieve Des Bois", 17, 3147),
    # YVELINES (78)
    "Versailles": MarketData("Versailles", 21, 7750),
    "Saint Germain En Laye": MarketData("Saint Germain En Laye", 22, 7919),
    "Poissy": MarketData("Poissy", 19, 4065),
    "Conflans Sainte Honorine": MarketData("Conflans Sainte Honorine", 19, 3623),
    "Mantes La Jolie": MarketData("Mantes La Jolie", 15, 2553),
    "Les Mureaux": MarketData("Les Mureaux", 15, 2259),
    "Plaisir": MarketData("Plaisir", 19, 3431),
    "Trappes": MarketData("Trappes", 17, 3007),
    "Rambouillet": MarketData("Rambouillet", 18, 4191),
    "Chatou": MarketData("Chatou", 24, 5252),
    "Le Chesnay Rocquencourt": MarketData("Le Chesnay Rocquencourt", 21, 5158),
    "Maisons Laffitte": MarketData("Maisons Laffitte", 22, 5943),
    "Houilles": MarketData("Houilles", 22, 5007),
    "Carrieres Sur Seine": MarketData("Carrieres Sur Seine", 22, 4833),
    "La Celle Saint Cloud": MarketData("La Celle Saint Cloud", 21, 4258),
    "Velizy Villacoublay": MarketData("Velizy Villacoublay", 20, 4812),
    "Montigny Le Bretonneux": MarketData("Montigny Le Bretonneux", 20, 4419),
    # SEINE-ET-MARNE (77)
    "Meaux": MarketData("Meaux", 16, 3124),
    "Melun": MarketData("Melun", 16, 2671),
    "Fontainebleau": MarketData("Fontainebleau", 16, 4859),
    "Chelles": MarketData("Chelles", 18, 3638),
    "Lagny Sur Marne": MarketData("Lagny Sur Marne", 18, 4042),
    "Bussy Saint Georges": MarketData("Bussy Saint Georges", 19, 4318),
    "Torcy": MarketData("Torcy", 18, 3420),
    "Pontault Combault": MarketData("Pontault Combault", 18, 3795),
    "Roissy En Brie": MarketData("Roissy En Brie", 17, 3646),
    "Ozoir La Ferriere": MarketData("Ozoir La Ferriere", 18, 4260),
    "Dammarie Les Lys": MarketData("Dammarie Les Lys", 16, 2636),
    "Combs La Ville": MarketData("Combs La Ville", 16, 3139),
    "Villeparisis": MarketData("Villeparisis", 18, 3147),
    # LYON (69)
    "Lyon 1Er": MarketData("Lyon 1Er", 18, 5278),
    "Lyon 2Eme": MarketData("Lyon 2Eme", 18, 5658),
    "Lyon 3Eme": MarketData("Lyon 3Eme", 17, 4561),
    "Lyon 4Eme": MarketData("Lyon 4Eme", 17, 5141),
    "Lyon 5Eme": MarketData("Lyon 5Eme", 17, 4265),
    "Lyon 6Eme": MarketData("Lyon 6Eme", 18, 5708),
    "Lyon 7Eme": MarketData("Lyon 7Eme", 16, 4559),
    "Lyon 8Eme": MarketData("Lyon 8Eme", 16, 3699),
    "Lyon 9Eme": MarketData("Lyon 9Eme", 15, 3721),
    "Villeurbanne": MarketData("Villeurbanne", 15, 3788),
    "Caluire Et Cuire": MarketData("Caluire Et Cuire", 16, 4051),
    "Venissieux": MarketData("Venissieux", 15, 2959),
    "Vaulx En Velin": MarketData("Vaulx En Velin", 14, 2671),
    "Saint Priest": MarketData("Saint Priest", 14, 3880),
}


# =============================================================================
# ILE-DE-FRANCE CITY PROFILES (from comprehensive analysis)
# Source: seloger_comprehensive_analysis.csv and seloger_comprehensive_analysis.py
# =============================================================================

IDF_CITY_PROFILES: Dict[str, CityProfile] = {
    # PARIS
    "Paris 1Er": CityProfile(
        "Paris 1Er",
        "75",
        safety=4,
        transport=5,
        growth=2,
        quality=4,
        amenities=5,
        notes="Tourist area, premium",
    ),
    "Paris 2Eme": CityProfile(
        "Paris 2Eme",
        "75",
        safety=4,
        transport=5,
        growth=2,
        quality=4,
        amenities=5,
        notes="Business district",
    ),
    "Paris 3Eme": CityProfile(
        "Paris 3Eme",
        "75",
        safety=4,
        transport=5,
        growth=2,
        quality=5,
        amenities=5,
        notes="Marais, trendy",
    ),
    "Paris 4Eme": CityProfile(
        "Paris 4Eme",
        "75",
        safety=4,
        transport=5,
        growth=2,
        quality=5,
        amenities=5,
        notes="Marais, premium",
    ),
    "Paris 5Eme": CityProfile(
        "Paris 5Eme",
        "75",
        safety=5,
        transport=5,
        growth=2,
        quality=5,
        amenities=5,
        notes="Latin Quarter",
    ),
    "Paris 6Eme": CityProfile(
        "Paris 6Eme",
        "75",
        safety=5,
        transport=5,
        growth=1,
        quality=5,
        amenities=5,
        notes="Saint-Germain, peak prices",
    ),
    "Paris 7Eme": CityProfile(
        "Paris 7Eme",
        "75",
        safety=5,
        transport=5,
        growth=1,
        quality=5,
        amenities=4,
        notes="Government, embassies",
    ),
    "Paris 8Eme": CityProfile(
        "Paris 8Eme",
        "75",
        safety=4,
        transport=5,
        growth=2,
        quality=4,
        amenities=5,
        notes="Champs-Élysées",
    ),
    "Paris 9Eme": CityProfile(
        "Paris 9Eme",
        "75",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=5,
        notes="Opéra, SoPi gentrifying",
    ),
    "Paris 10Eme": CityProfile(
        "Paris 10Eme",
        "75",
        safety=3,
        transport=5,
        growth=4,
        quality=4,
        amenities=5,
        notes="Canal St-Martin, gentrifying",
    ),
    "Paris 11Eme": CityProfile(
        "Paris 11Eme",
        "75",
        safety=3,
        transport=5,
        growth=3,
        quality=4,
        amenities=5,
        notes="Bastille, gentrified",
    ),
    "Paris 12Eme": CityProfile(
        "Paris 12Eme",
        "75",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        notes="Bercy, residential",
    ),
    "Paris 13Eme": CityProfile(
        "Paris 13Eme",
        "75",
        safety=3,
        transport=5,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        renewal=True,
        notes="Rive Gauche development",
    ),
    "Paris 14Eme": CityProfile(
        "Paris 14Eme",
        "75",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        notes="Montparnasse",
    ),
    "Paris 15Eme": CityProfile(
        "Paris 15Eme",
        "75",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        notes="Family residential",
    ),
    "Paris 16Eme": CityProfile(
        "Paris 16Eme",
        "75",
        safety=5,
        transport=5,
        growth=2,
        quality=5,
        amenities=4,
        notes="Wealthy, stable",
    ),
    "Paris 17Eme": CityProfile(
        "Paris 17Eme",
        "75",
        safety=4,
        transport=5,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        renewal=True,
        notes="Batignolles, M14",
    ),
    "Paris 18Eme": CityProfile(
        "Paris 18Eme",
        "75",
        safety=2,
        transport=5,
        growth=4,
        quality=3,
        amenities=4,
        renewal=True,
        notes="Montmartre/Goutte d'Or",
    ),
    "Paris 19Eme": CityProfile(
        "Paris 19Eme",
        "75",
        safety=2,
        transport=4,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        notes="Canal Ourcq, gentrifying",
    ),
    "Paris 20Eme": CityProfile(
        "Paris 20Eme",
        "75",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=4,
        renewal=True,
        notes="Belleville, artists",
    ),
    # SEINE-SAINT-DENIS (93) - High yields, challenging safety
    "Saint Denis": CityProfile(
        "Saint Denis",
        "93",
        safety=2,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        olympic=True,
        renewal=True,
        median_income=18000,
        unemployment_rate=18.0,
        notes="Olympics HQ, M15/16/17",
    ),
    "Saint Ouen": CityProfile(
        "Saint Ouen",
        "93",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        olympic=True,
        renewal=True,
        median_income=22000,
        unemployment_rate=14.0,
        notes="M14 extension, gentrifying",
    ),
    "Aubervilliers": CityProfile(
        "Aubervilliers",
        "93",
        safety=2,
        transport=5,
        growth=5,
        quality=2,
        amenities=3,
        grand_paris=True,
        olympic=True,
        renewal=True,
        median_income=17000,
        unemployment_rate=20.0,
        notes="Fort development, M15",
    ),
    "Pantin": CityProfile(
        "Pantin",
        "93",
        safety=3,
        transport=4,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=24000,
        unemployment_rate=13.0,
        notes="Creative industries",
    ),
    "Montreuil": CityProfile(
        "Montreuil",
        "93",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=26000,
        unemployment_rate=12.0,
        notes="Artists, already expensive",
    ),
    "Le Pre Saint Gervais": CityProfile(
        "Le Pre Saint Gervais",
        "93",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        median_income=25000,
        unemployment_rate=12.0,
        notes="Small, Paris spillover",
    ),
    "Les Lilas": CityProfile(
        "Les Lilas",
        "93",
        safety=4,
        transport=4,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=30000,
        unemployment_rate=10.0,
        notes="Nice, family-friendly",
    ),
    "Bagnolet": CityProfile(
        "Bagnolet",
        "93",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=23000,
        unemployment_rate=14.0,
        notes="Montreuil spillover",
    ),
    "Romainville": CityProfile(
        "Romainville",
        "93",
        safety=3,
        transport=3,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=22000,
        unemployment_rate=14.0,
        notes="M11 extension coming",
    ),
    "Noisy Le Sec": CityProfile(
        "Noisy Le Sec",
        "93",
        safety=2,
        transport=4,
        growth=3,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=19000,
        unemployment_rate=17.0,
        notes="RER E, some renewal",
    ),
    "Bondy": CityProfile(
        "Bondy",
        "93",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=18000,
        unemployment_rate=18.0,
        notes="Future M15",
    ),
    "Bobigny": CityProfile(
        "Bobigny",
        "93",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=17000,
        unemployment_rate=19.0,
        notes="Prefecture, renewal",
    ),
    "Drancy": CityProfile(
        "Drancy",
        "93",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=18000,
        unemployment_rate=17.0,
        notes="Future M16/17",
    ),
    "Le Bourget": CityProfile(
        "Le Bourget",
        "93",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=19000,
        unemployment_rate=16.0,
        notes="Airport, M16/17",
    ),
    "La Courneuve": CityProfile(
        "La Courneuve",
        "93",
        safety=1,
        transport=4,
        growth=4,
        quality=2,
        amenities=2,
        grand_paris=True,
        olympic=True,
        renewal=True,
        median_income=15000,
        unemployment_rate=22.0,
        notes="4000 area, major renewal",
    ),
    "Stains": CityProfile(
        "Stains",
        "93",
        safety=1,
        transport=3,
        growth=3,
        quality=2,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=14000,
        unemployment_rate=24.0,
        notes="Challenging, slow renewal",
    ),
    "Pierrefitte Sur Seine": CityProfile(
        "Pierrefitte Sur Seine",
        "93",
        safety=2,
        transport=3,
        growth=3,
        quality=2,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=16000,
        unemployment_rate=20.0,
        notes="RER D only",
    ),
    "Villetaneuse": CityProfile(
        "Villetaneuse",
        "93",
        safety=2,
        transport=3,
        growth=3,
        quality=2,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=15000,
        unemployment_rate=21.0,
        notes="University town",
    ),
    "Epinay Sur Seine": CityProfile(
        "Epinay Sur Seine",
        "93",
        safety=2,
        transport=3,
        growth=3,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=17000,
        unemployment_rate=18.0,
        notes="Mixed, some renewal",
    ),
    # HAUTS-DE-SEINE (92) - Premium suburbs
    "Boulogne Billancourt": CityProfile(
        "Boulogne Billancourt",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=5,
        amenities=5,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.0,
        notes="Premium, Ile Seguin",
    ),
    "Issy Les Moulineaux": CityProfile(
        "Issy Les Moulineaux",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=5,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=7.5,
        notes="Business hub",
    ),
    "Levallois Perret": CityProfile(
        "Levallois Perret",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=5,
        grand_paris=True,
        median_income=44000,
        unemployment_rate=7.0,
        notes="Dense, future M15",
    ),
    "Neuilly Sur Seine": CityProfile(
        "Neuilly Sur Seine",
        "92",
        safety=5,
        transport=5,
        growth=2,
        quality=5,
        amenities=5,
        grand_paris=True,
        median_income=65000,
        unemployment_rate=5.0,
        notes="Very wealthy",
    ),
    "Clichy": CityProfile(
        "Clichy",
        "92",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=28000,
        unemployment_rate=12.0,
        notes="M14, rapid gentrification",
    ),
    "Asnieres Sur Seine": CityProfile(
        "Asnieres Sur Seine",
        "92",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=32000,
        unemployment_rate=10.0,
        notes="Gentrifying, M15",
    ),
    "Courbevoie": CityProfile(
        "Courbevoie",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.5,
        notes="La Défense",
    ),
    "Puteaux": CityProfile(
        "Puteaux",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=45000,
        unemployment_rate=7.0,
        notes="La Défense",
    ),
    "Nanterre": CityProfile(
        "Nanterre",
        "92",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        olympic=True,
        renewal=True,
        median_income=28000,
        unemployment_rate=12.0,
        notes="Major hub, M15/18",
    ),
    "Gennevilliers": CityProfile(
        "Gennevilliers",
        "92",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=20000,
        unemployment_rate=16.0,
        notes="Industrial renewal",
    ),
    "Colombes": CityProfile(
        "Colombes",
        "92",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=30000,
        unemployment_rate=11.0,
        notes="Gentrifying, M15",
    ),
    "Rueil Malmaison": CityProfile(
        "Rueil Malmaison",
        "92",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=45000,
        unemployment_rate=7.0,
        notes="Family residential",
    ),
    "Suresnes": CityProfile(
        "Suresnes",
        "92",
        safety=4,
        transport=4,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=8.0,
        notes="M15 boost",
    ),
    "Montrouge": CityProfile(
        "Montrouge",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=38000,
        unemployment_rate=8.0,
        notes="M4, gentrified",
    ),
    "Malakoff": CityProfile(
        "Malakoff",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=35000,
        unemployment_rate=9.0,
        notes="M13, stable",
    ),
    "Vanves": CityProfile(
        "Vanves",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=7.5,
        notes="Family-friendly",
    ),
    "Clamart": CityProfile(
        "Clamart",
        "92",
        safety=4,
        transport=4,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.0,
        notes="Grand Paris station",
    ),
    "Meudon": CityProfile(
        "Meudon",
        "92",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=45000,
        unemployment_rate=6.5,
        notes="Forest, residential",
    ),
    "Chatillon": CityProfile(
        "Chatillon",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=38000,
        unemployment_rate=8.0,
        notes="M13, stable",
    ),
    "Bagneux": CityProfile(
        "Bagneux",
        "92",
        safety=3,
        transport=4,
        growth=5,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=26000,
        unemployment_rate=12.0,
        notes="M4 extension, game-changer",
    ),
    "Fontenay Aux Roses": CityProfile(
        "Fontenay Aux Roses",
        "92",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=8.0,
        notes="Residential",
    ),
    "Chatenay Malabry": CityProfile(
        "Chatenay Malabry",
        "92",
        safety=4,
        transport=4,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.5,
        notes="Forest, M18",
    ),
    "Sceaux": CityProfile(
        "Sceaux",
        "92",
        safety=5,
        transport=4,
        growth=2,
        quality=5,
        amenities=4,
        grand_paris=True,
        median_income=50000,
        unemployment_rate=6.0,
        notes="Bourgeois, RER B",
    ),
    "Antony": CityProfile(
        "Antony",
        "92",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.0,
        notes="RER B hub",
    ),
    # VAL-DE-MARNE (94)
    "Vincennes": CityProfile(
        "Vincennes",
        "94",
        safety=4,
        transport=5,
        growth=2,
        quality=5,
        amenities=5,
        grand_paris=True,
        median_income=45000,
        unemployment_rate=6.5,
        notes="Premium, near Bois",
    ),
    "Saint Mande": CityProfile(
        "Saint Mande",
        "94",
        safety=5,
        transport=5,
        growth=2,
        quality=5,
        amenities=4,
        grand_paris=True,
        median_income=50000,
        unemployment_rate=5.5,
        notes="Small, wealthy",
    ),
    "Charenton Le Pont": CityProfile(
        "Charenton Le Pont",
        "94",
        safety=4,
        transport=5,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.0,
        notes="Near Paris 12",
    ),
    "Ivry Sur Seine": CityProfile(
        "Ivry Sur Seine",
        "94",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=25000,
        unemployment_rate=13.0,
        notes="Major development",
    ),
    "Villejuif": CityProfile(
        "Villejuif",
        "94",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=27000,
        unemployment_rate=12.0,
        notes="Cancer campus, M15",
    ),
    "Vitry Sur Seine": CityProfile(
        "Vitry Sur Seine",
        "94",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=21000,
        unemployment_rate=15.0,
        notes="M15 will help",
    ),
    "Creteil": CityProfile(
        "Creteil",
        "94",
        safety=3,
        transport=5,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=26000,
        unemployment_rate=12.0,
        notes="Prefecture, M15",
    ),
    "Maisons Alfort": CityProfile(
        "Maisons Alfort",
        "94",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=35000,
        unemployment_rate=8.5,
        notes="Stable residential",
    ),
    "Alfortville": CityProfile(
        "Alfortville",
        "94",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=28000,
        unemployment_rate=11.0,
        notes="Near Ivry",
    ),
    "Cachan": CityProfile(
        "Cachan",
        "94",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=32000,
        unemployment_rate=9.0,
        notes="Student area",
    ),
    "Gentilly": CityProfile(
        "Gentilly",
        "94",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=27000,
        unemployment_rate=11.0,
        notes="Campus Grand Parc",
    ),
    "Le Kremlin Bicetre": CityProfile(
        "Le Kremlin Bicetre",
        "94",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=28000,
        unemployment_rate=11.0,
        notes="Hospital area",
    ),
    "Nogent Sur Marne": CityProfile(
        "Nogent Sur Marne",
        "94",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=42000,
        unemployment_rate=7.0,
        notes="Bourgeois, RER",
    ),
    "Fontenay Sous Bois": CityProfile(
        "Fontenay Sous Bois",
        "94",
        safety=3,
        transport=5,
        growth=5,
        quality=3,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=30000,
        unemployment_rate=10.0,
        notes="Val de Fontenay hub",
    ),
    "Champigny Sur Marne": CityProfile(
        "Champigny Sur Marne",
        "94",
        safety=2,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=24000,
        unemployment_rate=13.0,
        notes="M15 will transform",
    ),
    "Le Perreux Sur Marne": CityProfile(
        "Le Perreux Sur Marne",
        "94",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=38000,
        unemployment_rate=8.0,
        notes="Nice, Marne side",
    ),
    "Joinville Le Pont": CityProfile(
        "Joinville Le Pont",
        "94",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=7.5,
        notes="Bords de Marne",
    ),
    # VAL-D'OISE (95)
    "Argenteuil": CityProfile(
        "Argenteuil",
        "95",
        safety=2,
        transport=4,
        growth=4,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=22000,
        unemployment_rate=14.0,
        notes="M15 will help",
    ),
    "Sarcelles": CityProfile(
        "Sarcelles",
        "95",
        safety=1,
        transport=3,
        growth=3,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=15000,
        unemployment_rate=22.0,
        notes="Challenging, renewal",
    ),
    "Cergy": CityProfile(
        "Cergy",
        "95",
        safety=3,
        transport=4,
        growth=3,
        quality=3,
        amenities=4,
        median_income=26000,
        unemployment_rate=11.0,
        notes="University town",
    ),
    "Pontoise": CityProfile(
        "Pontoise",
        "95",
        safety=3,
        transport=4,
        growth=3,
        quality=3,
        amenities=4,
        median_income=28000,
        unemployment_rate=10.0,
        notes="Historic center",
    ),
    "Enghien Les Bains": CityProfile(
        "Enghien Les Bains",
        "95",
        safety=4,
        transport=4,
        growth=3,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=40000,
        unemployment_rate=7.5,
        notes="Spa/casino town",
    ),
    "Montmorency": CityProfile(
        "Montmorency",
        "95",
        safety=4,
        transport=3,
        growth=3,
        quality=4,
        amenities=3,
        median_income=38000,
        unemployment_rate=8.0,
        notes="Forest, quiet",
    ),
    "Eaubonne": CityProfile(
        "Eaubonne",
        "95",
        safety=3,
        transport=3,
        growth=3,
        quality=3,
        amenities=3,
        median_income=30000,
        unemployment_rate=10.0,
        notes="Residential",
    ),
    "Garges Les Gonesse": CityProfile(
        "Garges Les Gonesse",
        "95",
        safety=1,
        transport=3,
        growth=4,
        quality=2,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=14000,
        unemployment_rate=23.0,
        notes="M17 will help",
    ),
    "Bezons": CityProfile(
        "Bezons",
        "95",
        safety=3,
        transport=4,
        growth=4,
        quality=3,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=26000,
        unemployment_rate=11.0,
        notes="Gentrifying",
    ),
    "Herblay": CityProfile(
        "Herblay",
        "95",
        safety=3,
        transport=3,
        growth=3,
        quality=3,
        amenities=3,
        median_income=32000,
        unemployment_rate=9.0,
        notes="Residential",
    ),
    # ESSONNE (91)
    "Grigny": CityProfile(
        "Grigny",
        "91",
        safety=1,
        transport=2,
        growth=3,
        quality=1,
        amenities=2,
        grand_paris=True,
        renewal=True,
        median_income=12000,
        unemployment_rate=28.0,
        notes="Grande Borne, risky",
    ),
    "Ris Orangis": CityProfile(
        "Ris Orangis",
        "91",
        safety=2,
        transport=3,
        growth=3,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=20000,
        unemployment_rate=15.0,
        notes="Mixed",
    ),
    "Evry Courcouronnes": CityProfile(
        "Evry Courcouronnes",
        "91",
        safety=2,
        transport=4,
        growth=3,
        quality=2,
        amenities=4,
        grand_paris=True,
        renewal=True,
        median_income=21000,
        unemployment_rate=14.0,
        notes="Prefecture",
    ),
    "Corbeil Essonnes": CityProfile(
        "Corbeil Essonnes",
        "91",
        safety=2,
        transport=4,
        growth=3,
        quality=2,
        amenities=3,
        grand_paris=True,
        renewal=True,
        median_income=20000,
        unemployment_rate=16.0,
        notes="Some challenging areas",
    ),
    "Massy": CityProfile(
        "Massy",
        "91",
        safety=4,
        transport=5,
        growth=4,
        quality=3,
        amenities=4,
        grand_paris=True,
        median_income=35000,
        unemployment_rate=9.0,
        notes="TGV hub, M18",
    ),
    "Palaiseau": CityProfile(
        "Palaiseau",
        "91",
        safety=4,
        transport=4,
        growth=4,
        quality=4,
        amenities=4,
        grand_paris=True,
        median_income=38000,
        unemployment_rate=8.0,
        notes="Saclay plateau",
    ),
}

# Link market data to city profiles
for name, profile in IDF_CITY_PROFILES.items():
    if name in IDF_MARKET_DATA:
        profile.market_data = IDF_MARKET_DATA[name]


class MarketDataProvider:
    """Provider for market data lookup and queries."""

    def __init__(self):
        self.market_data = IDF_MARKET_DATA
        self.city_profiles = IDF_CITY_PROFILES

    def get_market_data(self, location: str) -> Optional[MarketData]:
        """Get market data for a location.

        Args:
            location: City name (e.g., "Montrouge", "Paris 15Eme")

        Returns:
            MarketData if found, None otherwise
        """
        # Try exact match first
        if location in self.market_data:
            return self.market_data[location]

        # Try title case
        title_location = location.title()
        if title_location in self.market_data:
            return self.market_data[title_location]

        # Try fuzzy match
        location_lower = location.lower().replace("-", " ").replace("_", " ")
        for name, data in self.market_data.items():
            if name.lower().replace("-", " ") == location_lower:
                return data

        return None

    def get_city_profile(self, location: str) -> Optional[CityProfile]:
        """Get city profile for a location."""
        # Try exact match first
        if location in self.city_profiles:
            return self.city_profiles[location]

        # Try title case
        title_location = location.title()
        if title_location in self.city_profiles:
            return self.city_profiles[title_location]

        # Try fuzzy match
        location_lower = location.lower().replace("-", " ").replace("_", " ")
        for name, profile in self.city_profiles.items():
            if name.lower().replace("-", " ") == location_lower:
                return profile

        return None

    def get_by_postal_code(self, postal_code: str) -> list[CityProfile]:
        """Get all cities in a postal code/department."""
        dept = postal_code[:2]
        return [
            profile
            for profile in self.city_profiles.values()
            if profile.department == dept
        ]

    def get_top_yields(self, n: int = 10) -> list[tuple[str, MarketData]]:
        """Get top N locations by gross yield."""
        sorted_data = sorted(
            self.market_data.items(), key=lambda x: x[1].gross_yield, reverse=True
        )
        return sorted_data[:n]

    def get_top_investment_scores(self, n: int = 10) -> list[tuple[str, CityProfile]]:
        """Get top N locations by investment score."""
        profiles_with_data = [
            (name, profile)
            for name, profile in self.city_profiles.items()
            if profile.market_data is not None
        ]
        sorted_profiles = sorted(
            profiles_with_data, key=lambda x: x[1].investment_score, reverse=True
        )
        return sorted_profiles[:n]

    def get_safe_investments(
        self, min_safety: int = 3, min_yield: float = 4.0
    ) -> list[CityProfile]:
        """Get cities with good safety AND yield."""
        results = []
        for profile in self.city_profiles.values():
            if profile.safety >= min_safety and profile.market_data:
                if profile.market_data.gross_yield >= min_yield:
                    results.append(profile)
        return sorted(results, key=lambda x: x.investment_score, reverse=True)

    def get_grand_paris_opportunities(self) -> list[CityProfile]:
        """Get cities with Grand Paris Express impact."""
        results = [
            profile
            for profile in self.city_profiles.values()
            if profile.grand_paris and profile.market_data
        ]
        return sorted(results, key=lambda x: x.growth, reverse=True)
