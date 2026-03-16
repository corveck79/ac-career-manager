"""
Driver Data — names, profiles, and tier slot constants.

Extracted from career_manager.py to keep the main module focused on career logic.
Imported by CareerManager at class level.
"""

# 120 globally unique driver names (covers all 106 driver slots across all tiers)
DRIVER_NAMES = [
    # 0-9
    "Marco Rossi",       "James Hunt",        "Pierre Dupont",     "Hans Mueller",
    "Carlos Rivera",     "Tom Bradley",       "Luca Ferrari",      "Alex Chen",
    "David Williams",    "Raj Patel",
    # 10-19
    "Sven Johansson",    "Omar Hassan",       "Kenji Tanaka",      "Igor Petrov",
    "Fabio Romano",      "Ethan Clark",       "Nina Kovac",        "Lucas Petit",
    "Aiden Burke",       "Zara Osman",
    # 20-29
    "Felipe Rodrigues",  "Jan van der Berg",  "Mikael Lindqvist",  "Antoine Moreau",
    "Sebastian Richter", "Takumi Nakamura",   "Ryan O'Connor",     "Dimitri Volkov",
    "Wei Zhang",         "Emre Yilmaz",
    # 30-39
    "Stefan Baumann",    "Liam Fitzgerald",   "Pablo Sanchez",     "Yuki Hashimoto",
    "Cristian Popescu",  "Max Hartmann",      "Nico Berger",       "Andre Hoffmann",
    "Kofi Mensah",       "Ravi Sharma",
    # 40-49
    "Jake Morrison",     "Thomas Leclerc",    "Giulio Conti",      "Magnus Eriksson",
    "Aleksei Nikitin",   "Hiro Matsuda",      "Kevin Walsh",       "Leon Braun",
    "Samir Khalil",      "Dante Moraes",
    # 50-59
    "Felix Bauer",       "Connor MacLeod",    "Victor Blanc",      "Matteo Gallo",
    "Oskar Wiklund",     "Tariq Nasser",      "Samuel Obi",        "Dario Conti",
    "Erik Larsen",       "Julian Richter",
    # 60-69
    "Baptiste Renard",   "Kai Nakamura",      "Tobias Schreiber",  "Lorenzo Marini",
    "Jack Thornton",     "Vladimir Kozlov",   "Yasuhiro Ito",      "Patrick Brennan",
    "Roberto Mancini",   "Hugo Lefevre",
    # 70-79
    "Christoph Weber",   "Nils Gunnarsson",   "Mehmet Ozkan",      "Benedikt Fischer",
    "Alvaro Delgado",    "Finn Andersen",     "Artem Sokolov",     "Raul Jimenez",
    "Enzo Palermo",      "Timothy Hooper",
    # 80-89
    "Francois Girard",   "Kazuki Yamamoto",   "Benjamin Koch",     "Cian Murphy",
    "Mateus Costa",      "Tomas Novak",       "Rafael Torres",     "Pieter de Vries",
    "Duncan Fraser",     "Alexei Morozov",
    # 90-99
    "Simon Bertrand",    "Stephan Kramer",    "Mattias Svensson",  "Davide Russo",
    "Callum Stewart",    "Timur Bakirov",     "Marco Bianchi",     "Arnaud Leblanc",
    "Hiroshi Watanabe",  "Edward Collins",
    # 100-109
    "Gerhard Mayer",     "Luca Gentile",      "Frederick Larsson", "Alistair Young",
    "Marco Colombo",     "Jean-Paul Tissot",  "Adriano Ferretti",  "Sebastian Vallet",
    "Diego Morales",     "Andrei Popov",
    # 110-119
    "Josef Novotny",     "Henryk Kowalski",   "Kwame Asante",      "Taiki Oshima",
    "Brenden Walsh",     "Giacomo Vietti",    "Emilio Fernandez",  "Lars Petersen",
    "Nikolai Volkov",    "Kim Andersen",
]

# Per-driver personality profiles.
# skill (70-95):      maps to AI_LEVEL offset in race.ini
# aggression (0-100): maps directly to AI_AGGRESSION in race.ini
# wet_skill (0-100):  AI_LEVEL bonus/penalty in wet weather (factor 0.06)
# quali_pace (0-100): displayed on driver card; gameplay effect reserved for future
# consistency (0-100): drives per-driver AI_LEVEL variance; low = more volatile
# nickname (str|None): paddock name shown on driver card; ~37 drivers have one
# nationality: 3-letter AC NATION_CODE, shown on profile card + race UI
# Style derived: skill>=85+aggr>=60=Charger, skill>=85+aggr<60=Tactician,
#                skill<85+aggr>=60=Wildcard, else=Journeyman
DRIVER_PROFILES = {
    # name                  nat    skill  aggr   wet   quali  cons  night  nickname
    "Marco Rossi":       {"nationality": "ITA", "skill": 88, "aggression": 72, "wet_skill": 62, "quali_pace": 80, "consistency": 52, "night_skill": 51, "nickname": "Red Mist"},
    "James Hunt":        {"nationality": "GBR", "skill": 91, "aggression": 85, "wet_skill": 55, "quali_pace": 94, "consistency": 48, "night_skill": 47, "nickname": "Apex Predator"},
    "Pierre Dupont":     {"nationality": "FRA", "skill": 76, "aggression": 30, "wet_skill": 72, "quali_pace": 68, "consistency": 85, "night_skill": 67, "nickname": None},
    "Hans Mueller":      {"nationality": "GER", "skill": 82, "aggression": 45, "wet_skill": 58, "quali_pace": 75, "consistency": 80, "night_skill": 62, "nickname": None},
    "Carlos Rivera":     {"nationality": "ESP", "skill": 79, "aggression": 60, "wet_skill": 50, "quali_pace": 72, "consistency": 60, "night_skill": 53, "nickname": None},
    "Tom Bradley":       {"nationality": "GBR", "skill": 74, "aggression": 20, "wet_skill": 65, "quali_pace": 55, "consistency": 88, "night_skill": 68, "nickname": None},
    "Luca Ferrari":      {"nationality": "ITA", "skill": 85, "aggression": 55, "wet_skill": 70, "quali_pace": 85, "consistency": 82, "night_skill": 64, "nickname": "Cold Blood"},
    "Alex Chen":         {"nationality": "CHN", "skill": 83, "aggression": 40, "wet_skill": 75, "quali_pace": 78, "consistency": 86, "night_skill": 67, "nickname": None},
    "David Williams":    {"nationality": "GBR", "skill": 70, "aggression": 15, "wet_skill": 78, "quali_pace": 55, "consistency": 90, "night_skill": 72, "nickname": None},
    "Raj Patel":         {"nationality": "IND", "skill": 77, "aggression": 50, "wet_skill": 55, "quali_pace": 65, "consistency": 72, "night_skill": 58, "nickname": None},
    "Sven Johansson":    {"nationality": "SWE", "skill": 80, "aggression": 35, "wet_skill": 82, "quali_pace": 70, "consistency": 84, "night_skill": 78, "nickname": "Rain King"},
    "Omar Hassan":       {"nationality": "MAR", "skill": 78, "aggression": 65, "wet_skill": 42, "quali_pace": 68, "consistency": 55, "night_skill": 49, "nickname": None},
    "Kenji Tanaka":      {"nationality": "JPN", "skill": 84, "aggression": 25, "wet_skill": 70, "quali_pace": 76, "consistency": 91, "night_skill": 85, "nickname": "Metronome"},
    "Igor Petrov":       {"nationality": "RUS", "skill": 86, "aggression": 70, "wet_skill": 60, "quali_pace": 82, "consistency": 55, "night_skill": 52, "nickname": None},
    "Fabio Romano":      {"nationality": "ITA", "skill": 89, "aggression": 80, "wet_skill": 45, "quali_pace": 86, "consistency": 52, "night_skill": 47, "nickname": "Last Lap Lunatic"},
    "Ethan Clark":       {"nationality": "GBR", "skill": 73, "aggression": 30, "wet_skill": 60, "quali_pace": 58, "consistency": 82, "night_skill": 64, "nickname": None},
    "Nina Kovac":        {"nationality": "CRO", "skill": 81, "aggression": 45, "wet_skill": 68, "quali_pace": 74, "consistency": 80, "night_skill": 64, "nickname": None},
    "Lucas Petit":       {"nationality": "FRA", "skill": 75, "aggression": 55, "wet_skill": 52, "quali_pace": 63, "consistency": 68, "night_skill": 56, "nickname": None},
    "Aiden Burke":       {"nationality": "IRL", "skill": 72, "aggression": 60, "wet_skill": 70, "quali_pace": 60, "consistency": 55, "night_skill": 55, "nickname": None},
    "Zara Osman":        {"nationality": "KEN", "skill": 77, "aggression": 40, "wet_skill": 58, "quali_pace": 65, "consistency": 78, "night_skill": 62, "nickname": None},
    "Felipe Rodrigues":  {"nationality": "BRA", "skill": 85, "aggression": 75, "wet_skill": 48, "quali_pace": 80, "consistency": 50, "night_skill": 48, "nickname": "Full Send"},
    "Jan van der Berg":  {"nationality": "NLD", "skill": 82, "aggression": 35, "wet_skill": 80, "quali_pace": 78, "consistency": 87, "night_skill": 69, "nickname": None},
    "Mikael Lindqvist":  {"nationality": "SWE", "skill": 79, "aggression": 20, "wet_skill": 85, "quali_pace": 65, "consistency": 91, "night_skill": 82, "nickname": "Wet Line"},
    "Antoine Moreau":    {"nationality": "FRA", "skill": 83, "aggression": 50, "wet_skill": 65, "quali_pace": 80, "consistency": 78, "night_skill": 62, "nickname": None},
    "Sebastian Richter": {"nationality": "GER", "skill": 90, "aggression": 65, "wet_skill": 68, "quali_pace": 88, "consistency": 60, "night_skill": 70, "nickname": "Precision"},
    "Takumi Nakamura":   {"nationality": "JPN", "skill": 87, "aggression": 30, "wet_skill": 82, "quali_pace": 70, "consistency": 94, "night_skill": 90, "nickname": "Clockwork"},
    "Ryan O'Connor":     {"nationality": "IRL", "skill": 76, "aggression": 70, "wet_skill": 72, "quali_pace": 65, "consistency": 48, "night_skill": 52, "nickname": "Risk Factor"},
    "Dimitri Volkov":    {"nationality": "RUS", "skill": 84, "aggression": 80, "wet_skill": 55, "quali_pace": 75, "consistency": 45, "night_skill": 47, "nickname": "Boom or Bust"},
    "Wei Zhang":         {"nationality": "CHN", "skill": 80, "aggression": 45, "wet_skill": 62, "quali_pace": 72, "consistency": 76, "night_skill": 61, "nickname": None},
    "Emre Yilmaz":       {"nationality": "TUR", "skill": 74, "aggression": 55, "wet_skill": 48, "quali_pace": 60, "consistency": 65, "night_skill": 54, "nickname": None},
    "Stefan Baumann":    {"nationality": "GER", "skill": 86, "aggression": 40, "wet_skill": 72, "quali_pace": 90, "consistency": 86, "night_skill": 67, "nickname": "Mr. Saturday"},
    "Liam Fitzgerald":   {"nationality": "IRL", "skill": 71, "aggression": 25, "wet_skill": 66, "quali_pace": 52, "consistency": 85, "night_skill": 67, "nickname": None},
    "Pablo Sanchez":     {"nationality": "ESP", "skill": 83, "aggression": 70, "wet_skill": 50, "quali_pace": 78, "consistency": 52, "night_skill": 49, "nickname": None},
    "Yuki Hashimoto":    {"nationality": "JPN", "skill": 78, "aggression": 35, "wet_skill": 75, "quali_pace": 68, "consistency": 86, "night_skill": 68, "nickname": None},
    "Cristian Popescu":  {"nationality": "ROU", "skill": 76, "aggression": 50, "wet_skill": 55, "quali_pace": 62, "consistency": 70, "night_skill": 58, "nickname": None},
    "Max Hartmann":      {"nationality": "GER", "skill": 85, "aggression": 60, "wet_skill": 65, "quali_pace": 85, "consistency": 68, "night_skill": 58, "nickname": None},
    "Nico Berger":       {"nationality": "GER", "skill": 88, "aggression": 50, "wet_skill": 70, "quali_pace": 92, "consistency": 82, "night_skill": 78, "nickname": "Ice Brain"},
    "Andre Hoffmann":    {"nationality": "GER", "skill": 77, "aggression": 35, "wet_skill": 60, "quali_pace": 65, "consistency": 80, "night_skill": 63, "nickname": None},
    "Kofi Mensah":       {"nationality": "GHA", "skill": 81, "aggression": 55, "wet_skill": 52, "quali_pace": 70, "consistency": 72, "night_skill": 57, "nickname": None},
    "Ravi Sharma":       {"nationality": "IND", "skill": 75, "aggression": 40, "wet_skill": 45, "quali_pace": 60, "consistency": 75, "night_skill": 58, "nickname": None},
    "Jake Morrison":     {"nationality": "GBR", "skill": 73, "aggression": 65, "wet_skill": 60, "quali_pace": 58, "consistency": 50, "night_skill": 51, "nickname": None},
    "Thomas Leclerc":    {"nationality": "FRA", "skill": 87, "aggression": 45, "wet_skill": 78, "quali_pace": 88, "consistency": 88, "night_skill": 82, "nickname": "The Surgeon"},
    "Giulio Conti":      {"nationality": "ITA", "skill": 82, "aggression": 75, "wet_skill": 45, "quali_pace": 75, "consistency": 48, "night_skill": 46, "nickname": "Chaos Engine"},
    "Magnus Eriksson":   {"nationality": "SWE", "skill": 79, "aggression": 20, "wet_skill": 80, "quali_pace": 62, "consistency": 90, "night_skill": 72, "nickname": None},
    "Aleksei Nikitin":   {"nationality": "RUS", "skill": 84, "aggression": 60, "wet_skill": 58, "quali_pace": 78, "consistency": 58, "night_skill": 54, "nickname": None},
    "Hiro Matsuda":      {"nationality": "JPN", "skill": 88, "aggression": 35, "wet_skill": 85, "quali_pace": 82, "consistency": 90, "night_skill": 82, "nickname": "Storm Pace"},
    "Kevin Walsh":       {"nationality": "IRL", "skill": 71, "aggression": 50, "wet_skill": 62, "quali_pace": 55, "consistency": 72, "night_skill": 60, "nickname": None},
    "Leon Braun":        {"nationality": "GER", "skill": 76, "aggression": 30, "wet_skill": 58, "quali_pace": 62, "consistency": 82, "night_skill": 64, "nickname": None},
    "Samir Khalil":      {"nationality": "MAR", "skill": 80, "aggression": 65, "wet_skill": 38, "quali_pace": 68, "consistency": 55, "night_skill": 48, "nickname": None},
    "Dante Moraes":      {"nationality": "BRA", "skill": 83, "aggression": 85, "wet_skill": 88, "quali_pace": 80, "consistency": 42, "night_skill": 52, "nickname": "Storm"},
    "Felix Bauer":       {"nationality": "GER", "skill": 86, "aggression": 40, "wet_skill": 68, "quali_pace": 88, "consistency": 85, "night_skill": 66, "nickname": None},
    "Connor MacLeod":    {"nationality": "GBR", "skill": 74, "aggression": 55, "wet_skill": 65, "quali_pace": 60, "consistency": 68, "night_skill": 58, "nickname": None},
    "Victor Blanc":      {"nationality": "FRA", "skill": 81, "aggression": 30, "wet_skill": 70, "quali_pace": 75, "consistency": 88, "night_skill": 75, "nickname": "Zero Drama"},
    "Matteo Gallo":      {"nationality": "ITA", "skill": 85, "aggression": 70, "wet_skill": 52, "quali_pace": 80, "consistency": 55, "night_skill": 50, "nickname": None},
    "Oskar Wiklund":     {"nationality": "SWE", "skill": 77, "aggression": 20, "wet_skill": 82, "quali_pace": 60, "consistency": 90, "night_skill": 72, "nickname": None},
    "Tariq Nasser":      {"nationality": "MAR", "skill": 79, "aggression": 60, "wet_skill": 38, "quali_pace": 65, "consistency": 58, "night_skill": 50, "nickname": None},
    "Samuel Obi":        {"nationality": "GBR", "skill": 72, "aggression": 45, "wet_skill": 60, "quali_pace": 55, "consistency": 75, "night_skill": 61, "nickname": None},
    "Dario Conti":       {"nationality": "ITA", "skill": 87, "aggression": 75, "wet_skill": 50, "quali_pace": 82, "consistency": 52, "night_skill": 49, "nickname": "The Enforcer"},
    "Erik Larsen":       {"nationality": "SWE", "skill": 80, "aggression": 30, "wet_skill": 80, "quali_pace": 68, "consistency": 86, "night_skill": 69, "nickname": None},
    "Julian Richter":    {"nationality": "GER", "skill": 84, "aggression": 55, "wet_skill": 62, "quali_pace": 80, "consistency": 78, "night_skill": 61, "nickname": None},
    "Baptiste Renard":   {"nationality": "FRA", "skill": 78, "aggression": 40, "wet_skill": 65, "quali_pace": 70, "consistency": 80, "night_skill": 64, "nickname": None},
    "Kai Nakamura":      {"nationality": "JPN", "skill": 82, "aggression": 25, "wet_skill": 78, "quali_pace": 72, "consistency": 90, "night_skill": 71, "nickname": None},
    "Tobias Schreiber":  {"nationality": "GER", "skill": 75, "aggression": 50, "wet_skill": 55, "quali_pace": 62, "consistency": 72, "night_skill": 58, "nickname": None},
    "Lorenzo Marini":    {"nationality": "ITA", "skill": 89, "aggression": 80, "wet_skill": 48, "quali_pace": 88, "consistency": 50, "night_skill": 92, "nickname": "Night Hunter"},
    "Jack Thornton":     {"nationality": "GBR", "skill": 83, "aggression": 65, "wet_skill": 62, "quali_pace": 75, "consistency": 58, "night_skill": 54, "nickname": "Late Charge"},
    "Vladimir Kozlov":   {"nationality": "RUS", "skill": 77, "aggression": 85, "wet_skill": 52, "quali_pace": 60, "consistency": 40, "night_skill": 44, "nickname": "The Gambler"},
    "Yasuhiro Ito":      {"nationality": "JPN", "skill": 86, "aggression": 20, "wet_skill": 88, "quali_pace": 78, "consistency": 95, "night_skill": 88, "nickname": "Iron Pace"},
    "Patrick Brennan":   {"nationality": "IRL", "skill": 74, "aggression": 45, "wet_skill": 68, "quali_pace": 58, "consistency": 75, "night_skill": 62, "nickname": None},
    "Roberto Mancini":   {"nationality": "ITA", "skill": 80, "aggression": 60, "wet_skill": 55, "quali_pace": 70, "consistency": 60, "night_skill": 54, "nickname": None},
    "Hugo Lefevre":      {"nationality": "FRA", "skill": 73, "aggression": 35, "wet_skill": 62, "quali_pace": 55, "consistency": 80, "night_skill": 63, "nickname": None},
    "Christoph Weber":   {"nationality": "GER", "skill": 88, "aggression": 50, "wet_skill": 72, "quali_pace": 90, "consistency": 84, "night_skill": 78, "nickname": "The Mastermind"},
    "Nils Gunnarsson":   {"nationality": "SWE", "skill": 82, "aggression": 25, "wet_skill": 85, "quali_pace": 68, "consistency": 92, "night_skill": 73, "nickname": None},
    "Mehmet Ozkan":      {"nationality": "TUR", "skill": 79, "aggression": 70, "wet_skill": 42, "quali_pace": 65, "consistency": 50, "night_skill": 47, "nickname": None},
    "Benedikt Fischer":  {"nationality": "GER", "skill": 85, "aggression": 40, "wet_skill": 70, "quali_pace": 86, "consistency": 85, "night_skill": 66, "nickname": None},
    "Alvaro Delgado":    {"nationality": "ESP", "skill": 83, "aggression": 65, "wet_skill": 48, "quali_pace": 75, "consistency": 55, "night_skill": 50, "nickname": None},
    "Finn Andersen":     {"nationality": "SWE", "skill": 76, "aggression": 30, "wet_skill": 80, "quali_pace": 60, "consistency": 86, "night_skill": 69, "nickname": None},
    "Artem Sokolov":     {"nationality": "RUS", "skill": 87, "aggression": 75, "wet_skill": 55, "quali_pace": 82, "consistency": 50, "night_skill": 49, "nickname": "Iron Fist"},
    "Raul Jimenez":      {"nationality": "ESP", "skill": 81, "aggression": 55, "wet_skill": 52, "quali_pace": 72, "consistency": 72, "night_skill": 57, "nickname": None},
    "Enzo Palermo":      {"nationality": "ITA", "skill": 84, "aggression": 80, "wet_skill": 45, "quali_pace": 76, "consistency": 45, "night_skill": 45, "nickname": "Raw Speed"},
    "Timothy Hooper":    {"nationality": "GBR", "skill": 70, "aggression": 20, "wet_skill": 68, "quali_pace": 48, "consistency": 88, "night_skill": 69, "nickname": None},
    "Francois Girard":   {"nationality": "FRA", "skill": 86, "aggression": 45, "wet_skill": 75, "quali_pace": 88, "consistency": 84, "night_skill": 66, "nickname": None},
    "Kazuki Yamamoto":   {"nationality": "JPN", "skill": 91, "aggression": 30, "wet_skill": 80, "quali_pace": 90, "consistency": 92, "night_skill": 85, "nickname": "Ice Cold"},
    "Benjamin Koch":     {"nationality": "GER", "skill": 78, "aggression": 60, "wet_skill": 55, "quali_pace": 65, "consistency": 58, "night_skill": 53, "nickname": None},
    "Cian Murphy":       {"nationality": "IRL", "skill": 73, "aggression": 50, "wet_skill": 68, "quali_pace": 55, "consistency": 72, "night_skill": 61, "nickname": None},
    "Mateus Costa":      {"nationality": "BRA", "skill": 82, "aggression": 70, "wet_skill": 60, "quali_pace": 75, "consistency": 52, "night_skill": 51, "nickname": None},
    "Tomas Novak":       {"nationality": "CZE", "skill": 79, "aggression": 35, "wet_skill": 65, "quali_pace": 65, "consistency": 82, "night_skill": 65, "nickname": None},
    "Rafael Torres":     {"nationality": "ESP", "skill": 85, "aggression": 75, "wet_skill": 52, "quali_pace": 82, "consistency": 52, "night_skill": 49, "nickname": "Frontline"},
    "Pieter de Vries":   {"nationality": "NLD", "skill": 83, "aggression": 40, "wet_skill": 82, "quali_pace": 78, "consistency": 84, "night_skill": 68, "nickname": None},
    "Duncan Fraser":     {"nationality": "GBR", "skill": 77, "aggression": 55, "wet_skill": 70, "quali_pace": 65, "consistency": 74, "night_skill": 61, "nickname": None},
    "Alexei Morozov":    {"nationality": "RUS", "skill": 80, "aggression": 65, "wet_skill": 48, "quali_pace": 68, "consistency": 55, "night_skill": 50, "nickname": None},
    "Simon Bertrand":    {"nationality": "FRA", "skill": 86, "aggression": 35, "wet_skill": 78, "quali_pace": 88, "consistency": 88, "night_skill": 78, "nickname": "Clean Air"},
    "Stephan Kramer":    {"nationality": "GER", "skill": 88, "aggression": 60, "wet_skill": 65, "quali_pace": 90, "consistency": 68, "night_skill": 58, "nickname": "The Dominator"},
    "Mattias Svensson":  {"nationality": "SWE", "skill": 82, "aggression": 25, "wet_skill": 85, "quali_pace": 68, "consistency": 90, "night_skill": 72, "nickname": None},
    "Davide Russo":      {"nationality": "ITA", "skill": 84, "aggression": 70, "wet_skill": 50, "quali_pace": 75, "consistency": 55, "night_skill": 50, "nickname": None},
    "Callum Stewart":    {"nationality": "GBR", "skill": 76, "aggression": 45, "wet_skill": 65, "quali_pace": 62, "consistency": 76, "night_skill": 62, "nickname": None},
    "Timur Bakirov":     {"nationality": "RUS", "skill": 79, "aggression": 80, "wet_skill": 45, "quali_pace": 62, "consistency": 42, "night_skill": 44, "nickname": "The Maverick"},
    "Marco Bianchi":     {"nationality": "ITA", "skill": 87, "aggression": 55, "wet_skill": 68, "quali_pace": 84, "consistency": 82, "night_skill": 63, "nickname": None},
    "Arnaud Leblanc":    {"nationality": "FRA", "skill": 81, "aggression": 35, "wet_skill": 72, "quali_pace": 72, "consistency": 84, "night_skill": 67, "nickname": None},
    "Hiroshi Watanabe":  {"nationality": "JPN", "skill": 85, "aggression": 20, "wet_skill": 88, "quali_pace": 75, "consistency": 95, "night_skill": 90, "nickname": "Stint Master"},
    "Edward Collins":    {"nationality": "GBR", "skill": 73, "aggression": 50, "wet_skill": 60, "quali_pace": 58, "consistency": 72, "night_skill": 59, "nickname": None},
    "Gerhard Mayer":     {"nationality": "GER", "skill": 83, "aggression": 45, "wet_skill": 65, "quali_pace": 78, "consistency": 80, "night_skill": 63, "nickname": None},
    "Luca Gentile":      {"nationality": "ITA", "skill": 89, "aggression": 70, "wet_skill": 55, "quali_pace": 86, "consistency": 58, "night_skill": 92, "nickname": "Night Hawk"},
    "Frederick Larsson": {"nationality": "SWE", "skill": 80, "aggression": 30, "wet_skill": 82, "quali_pace": 68, "consistency": 87, "night_skill": 70, "nickname": None},
    "Alistair Young":    {"nationality": "GBR", "skill": 76, "aggression": 55, "wet_skill": 62, "quali_pace": 62, "consistency": 70, "night_skill": 58, "nickname": None},
    "Marco Colombo":     {"nationality": "ITA", "skill": 85, "aggression": 65, "wet_skill": 58, "quali_pace": 82, "consistency": 62, "night_skill": 54, "nickname": None},
    "Jean-Paul Tissot":  {"nationality": "FRA", "skill": 82, "aggression": 40, "wet_skill": 68, "quali_pace": 75, "consistency": 82, "night_skill": 65, "nickname": None},
    "Adriano Ferretti":  {"nationality": "ITA", "skill": 87, "aggression": 80, "wet_skill": 45, "quali_pace": 84, "consistency": 48, "night_skill": 46, "nickname": "The Predator"},
    "Sebastian Vallet":  {"nationality": "FRA", "skill": 78, "aggression": 35, "wet_skill": 65, "quali_pace": 68, "consistency": 82, "night_skill": 65, "nickname": None},
    "Diego Morales":     {"nationality": "ESP", "skill": 83, "aggression": 60, "wet_skill": 48, "quali_pace": 72, "consistency": 58, "night_skill": 52, "nickname": None},
    "Andrei Popov":      {"nationality": "RUS", "skill": 81, "aggression": 50, "wet_skill": 55, "quali_pace": 70, "consistency": 72, "night_skill": 58, "nickname": None},
    "Josef Novotny":     {"nationality": "CZE", "skill": 75, "aggression": 40, "wet_skill": 62, "quali_pace": 60, "consistency": 78, "night_skill": 62, "nickname": None},
    "Henryk Kowalski":   {"nationality": "POL", "skill": 79, "aggression": 55, "wet_skill": 60, "quali_pace": 65, "consistency": 72, "night_skill": 59, "nickname": None},
    "Kwame Asante":      {"nationality": "GHA", "skill": 82, "aggression": 45, "wet_skill": 50, "quali_pace": 72, "consistency": 78, "night_skill": 59, "nickname": None},
    "Taiki Oshima":      {"nationality": "JPN", "skill": 86, "aggression": 30, "wet_skill": 85, "quali_pace": 82, "consistency": 92, "night_skill": 82, "nickname": "The Closer"},
    "Brenden Walsh":     {"nationality": "IRL", "skill": 71, "aggression": 65, "wet_skill": 70, "quali_pace": 55, "consistency": 48, "night_skill": 52, "nickname": "Raw Talent"},
    "Giacomo Vietti":    {"nationality": "ITA", "skill": 84, "aggression": 75, "wet_skill": 48, "quali_pace": 75, "consistency": 48, "night_skill": 47, "nickname": None},
    "Emilio Fernandez":  {"nationality": "ESP", "skill": 80, "aggression": 60, "wet_skill": 45, "quali_pace": 68, "consistency": 58, "night_skill": 51, "nickname": None},
    "Lars Petersen":     {"nationality": "SWE", "skill": 77, "aggression": 25, "wet_skill": 80, "quali_pace": 62, "consistency": 88, "night_skill": 70, "nickname": None},
    "Nikolai Volkov":    {"nationality": "RUS", "skill": 83, "aggression": 70, "wet_skill": 50, "quali_pace": 72, "consistency": 52, "night_skill": 49, "nickname": None},
    "Kim Andersen":      {"nationality": "SWE", "skill": 78, "aggression": 35, "wet_skill": 78, "quali_pace": 65, "consistency": 84, "night_skill": 68, "nickname": None},
}

# How many championship drivers per team entry (MX5 is single-driver; GT3/GT4/WEC are 2)
DRIVERS_PER_TEAM = {'mx5_cup': 1, 'gt4': 2, 'gt3': 2, 'wec': 2}

# Global driver slot offset per tier:
#   MX5:  14 teams x 1 = 14 drivers  -> slots  0-13
#   GT4:  16 teams x 2 = 32 drivers  -> slots 14-45
#   GT3:  20 teams x 2 = 40 drivers  -> slots 46-85
#   WEC:  10 teams x 2 = 20 drivers  -> slots 86-105
TIER_SLOT_OFFSET = {'mx5_cup': 0, 'gt4': 14, 'gt3': 46, 'wec': 86}


def get_driver_style(skill, aggression):
    """Return driver archetype based on skill + aggression."""
    if skill >= 85 and aggression >= 60: return "The Charger"
    if skill >= 85 and aggression <  60: return "The Tactician"
    if skill <  85 and aggression >= 60: return "The Wildcard"
    return "The Journeyman"


# Per-driver track type preference: 'fast', 'technical', or 'balanced' (default).
# On a matching track type, driver gets +1 AI_LEVEL; on a mismatched type, -1.
# Only non-balanced entries listed here; omitted drivers default to 'balanced'.
TRACK_PREFERENCES = {
    # --- Fast preference (high-speed circuits: Monza, Spa, Silverstone GP, Nürburgring GP) ---
    "James Hunt":        "fast",
    "Igor Petrov":       "fast",
    "Fabio Romano":      "fast",
    "Felipe Rodrigues":  "fast",
    "Sebastian Richter": "fast",
    "Dimitri Volkov":    "fast",
    "Pablo Sanchez":     "fast",
    "Max Hartmann":      "fast",
    "Aleksei Nikitin":   "fast",
    "Matteo Gallo":      "fast",
    "Dario Conti":       "fast",
    "Lorenzo Marini":    "fast",
    "Jack Thornton":     "fast",
    "Artem Sokolov":     "fast",
    "Enzo Palermo":      "fast",
    "Stephan Kramer":    "fast",
    "Davide Russo":      "fast",
    "Adriano Ferretti":  "fast",
    "Marco Colombo":     "fast",
    "Giacomo Vietti":    "fast",
    "Nikolai Volkov":    "fast",
    "Rafael Torres":     "fast",
    "Diego Morales":     "fast",
    "Emilio Fernandez":  "fast",
    "Vladimir Kozlov":   "fast",
    "Timur Bakirov":     "fast",
    "Dante Moraes":      "fast",
    "Mateus Costa":       "fast",
    "Giulio Conti":      "fast",
    "Roberto Mancini":   "fast",
    "Luca Gentile":      "fast",
    # --- Technical preference (short/twisty: Brands Hatch, Magione, Vallelunga, Silverstone Nat) ---
    "Pierre Dupont":     "technical",
    "Tom Bradley":       "technical",
    "Kenji Tanaka":      "technical",
    "Sven Johansson":    "technical",
    "Takumi Nakamura":   "technical",
    "Mikael Lindqvist":  "technical",
    "Yuki Hashimoto":    "technical",
    "Hiro Matsuda":      "technical",
    "Magnus Eriksson":   "technical",
    "Oskar Wiklund":     "technical",
    "Victor Blanc":      "technical",
    "Kai Nakamura":      "technical",
    "Yasuhiro Ito":      "technical",
    "Nils Gunnarsson":   "technical",
    "Finn Andersen":     "technical",
    "Erik Larsen":       "technical",
    "Hiroshi Watanabe":  "technical",
    "Mattias Svensson":  "technical",
    "Lars Petersen":     "technical",
    "Kim Andersen":      "technical",
    "Frederick Larsson": "technical",
    "Thomas Leclerc":    "technical",
    "Alex Chen":         "technical",
    "Pieter de Vries":   "technical",
    "Taiki Oshima":      "technical",
    "David Williams":    "technical",
    "Liam Fitzgerald":   "technical",
    "Arnaud Leblanc":    "technical",
    "Simon Bertrand":    "technical",
    "Tomas Novak":       "technical",
    "Baptiste Renard":   "technical",
    # All remaining drivers (not listed) default to 'balanced'.
}
