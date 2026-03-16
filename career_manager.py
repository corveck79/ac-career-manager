"""
Career Manager - Game Logic
Handles tiers, teams, contracts, race generation
"""

import json
import random
import hashlib
from datetime import datetime
import subprocess
import os

from platform_paths import get_ac_docs_path, is_linux


class CareerManager:
    """Main career management system"""

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
    #   MX5:  14 teams × 1 = 14 drivers  → slots  0-13
    #   GT4:  16 teams × 2 = 32 drivers  → slots 14-45
    #   GT3:  20 teams × 2 = 40 drivers  → slots 46-85
    #   WEC:  10 teams × 2 = 20 drivers  → slots 86-105
    TIER_SLOT_OFFSET = {'mx5_cup': 0, 'gt4': 14, 'gt3': 46, 'wec': 86}

    def __init__(self, config):
        self.config = config
        self.tiers = ['mx5_cup', 'gt4', 'gt3', 'wec']
        self._procedural_name_cache = {}
        self.tier_names = {
            'mx5_cup': 'MX5 Cup',
            'gt4':     'GT4 SuperCup',
            'gt3':     'British GT GT3',
            'wec':     'WEC / Elite'
        }

    def _get_style(self, skill, aggression):
        """Return driver archetype based on skill + aggression."""
        if skill >= 85 and aggression >= 60: return "The Charger"
        if skill >= 85 and aggression <  60: return "The Tactician"
        if skill <  85 and aggression >= 60: return "The Wildcard"
        return "The Journeyman"

    def get_driver_profile(self, name, career_data=None):
        """Return profile dict for a driver name, with derived style field."""
        p = dict(self.DRIVER_PROFILES.get(name, {"nationality": "GBR", "skill": 80, "aggression": 40}))
        if career_data:
            progress = (career_data.get('driver_progress') or {}).get(name, {})
            current = progress.get('current') or {}
            for key in ['skill', 'aggression', 'wet_skill', 'quali_pace', 'consistency']:
                if key in current:
                    p[key] = int(round(float(current[key])))
        return {**p, "style": self._get_style(p["skill"], p["aggression"])}

    def get_tier_info(self, tier_index):
        """Get tier configuration by index"""
        tier_name = self.tiers[tier_index]
        return self.config['tiers'][tier_name]

    def get_tier_races(self, career_data=None):
        """Get total races for the player's current tier (= length of track list)."""
        if career_data is None:
            return self.config['seasons'].get('races_per_tier', 10)
        tier_key  = self.tiers[career_data.get('tier', 0)]
        tier_info = self.config['tiers'][tier_key]
        cs        = career_data.get('career_settings') or {}
        tracks    = (cs.get('custom_tracks') or {}).get(tier_key) or tier_info['tracks']
        return len(tracks)

    # ------------------------------------------------------------------
    # Race generation
    # ------------------------------------------------------------------

    def generate_race(self, tier_info, race_num, team_name, car,
                      tier_key=None, season=1, weather_mode='realistic', night_cycle=True,
                      career_data=None):
        """Generate next race configuration.
        weather_mode: 'realistic' (default pool) | 'always_clear' | 'wet_challenge'
        night_cycle: if True and laps >= 30, enables time-of-day progression via SUN_ANGLE + TIME_OF_DAY_MULT
        """
        tracks = tier_info['tracks']
        track = tracks[(race_num - 1) % len(tracks)]

        ai_difficulty = self._calculate_ai_difficulty(team_name, tier_info)
        opponents = self._generate_opponent_field(tier_info, race_num, tier_key=tier_key,
                                                  season=season, career_data=career_data)

        weather = self._pick_weather(tier_info['race_format'], track, weather_mode=weather_mode)

        laps = (tier_info['race_laps'][race_num - 1]
                if tier_info.get('race_laps') and (race_num - 1) < len(tier_info['race_laps'])
                else tier_info['race_format'].get('laps', 20))

        # Night cycle: endurance races (>= 30 laps) get 1 full 24h day-night cycle
        sun_angle        = None
        time_of_day_mult = None
        if night_cycle and laps >= 30:
            race_hours       = laps * 2 / 60
            time_of_day_mult = max(8, round(24 / race_hours))
            sun_angle        = 40  # ~14:00 start → dark at 1/3, dawn at 2/3

        return {
            'race_num':         race_num,
            'track':            track,
            'car':              car,
            'team':             team_name,
            'ai_difficulty':    ai_difficulty,
            'opponents':        opponents,
            'laps':             laps,
            'time_limit':       tier_info['race_format'].get('time_limit_minutes', 45),
            'practice_minutes': tier_info['race_format'].get('practice_minutes', 10),
            'quali_minutes':    tier_info['race_format'].get('quali_minutes', 10),
            'weather':          weather,
            'sun_angle':        sun_angle,
            'time_of_day_mult': time_of_day_mult,
        }

    # Tracks that have wet weather support in vanilla AC
    WET_TRACKS = {
        'spa', 'monza', 'mugello', 'imola',
        'ks_silverstone', 'ks_brands_hatch',
        'ks_red_bull_ring', 'ks_vallelunga',
    }

    def _pick_weather(self, race_format, track, weather_mode='realistic'):
        """Pick a weather preset.
        weather_mode:
          'always_clear'  → always 3_clear
          'wet_challenge' → mostly wet / heavy cloud
          'csp_pure'      → dramatic mix, maximises CSP Pure visual range
          'realistic'     → use the tier's weighted weather_pool (default)
        Falls back to 7_heavy_clouds if wet is picked on an unsupported track.
        """
        if weather_mode == 'always_clear':
            return '3_clear'

        if weather_mode == 'wet_challenge':
            pool = [['wet', 60], ['7_heavy_clouds', 30], ['4_mid_clear', 10]]
        elif weather_mode == 'csp_pure':
            # Dramatic mix — maximises Pure Weather FX visual range
            pool = [['7_heavy_clouds', 30], ['wet', 25], ['6_light_clouds', 20],
                    ['4_mid_clear', 15], ['3_clear', 10]]
        else:  # realistic
            pool = race_format.get('weather_pool', [['3_clear', 100]])

        presets = [p[0] for p in pool]
        weights = [p[1] for p in pool]
        chosen  = random.choices(presets, weights=weights, k=1)[0]

        if chosen == 'wet':
            track_folder = track.split('/')[0]
            if track_folder not in self.WET_TRACKS:
                chosen = '7_heavy_clouds'  # fallback: overcast but no rain

        return chosen

    def _calculate_ai_difficulty(self, team_name, tier_info):
        base = self.config['difficulty']['base_ai_level']
        adj  = tier_info['ai_difficulty']
        var  = random.uniform(
            -self.config['difficulty']['ai_variance'],
             self.config['difficulty']['ai_variance']
        )
        return max(60, min(100, base + adj + var))

    def _generate_opponent_field(self, tier_info, race_num, tier_key=None, season=1, career_data=None):
        opponents = []
        offset = self.TIER_SLOT_OFFSET.get(tier_key, 0) if tier_key else 0
        dpt    = self.DRIVERS_PER_TEAM.get(tier_key, 1) if tier_key else 1
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode = self._get_name_mode(career_data)
        for i, team in enumerate(tier_info['teams']):
            perf = team.get('performance', 0) + random.uniform(-0.5, 0.5)
            global_slot = offset + i * dpt
            driver_name = self._get_driver_name(
                global_slot, season, career_seed, name_mode
            ) if tier_key else None
            opponents.append({
                'number':      i + 1,
                'team':        team['name'],
                'car':         team['car'],
                'tier':        team.get('tier', 'customer'),
                'performance': perf,
                'driver_name': driver_name,
                'global_slot': global_slot,
            })
        return opponents

    # ------------------------------------------------------------------
    # Weekend simulation — practice and qualifying results
    # ------------------------------------------------------------------

    def simulate_qualifying(self, opponents, ai_lvl, career_data=None):
        """Simulate qualifying for all opponents + player.

        Each driver runs 3 hot laps (take best). Pace is driven by quali_pace
        and car performance; consistency determines lap-to-lap variance.

        Returns list sorted P1→last:
            [{'name', 'car', 'team', 'is_player', 'pace_score', 'position'}, ...]
        """
        player_team = (career_data or {}).get('team')
        results = []
        for opp in opponents[:19]:
            if player_team and opp.get('team') == player_team:
                continue  # player fills this slot — skip the AI stand-in
            name    = opp.get('driver_name') or ''
            profile = self.get_driver_profile(name, career_data=career_data)
            base    = opp.get('performance', 0) + (profile.get('quali_pace', 75) - 75) * 0.4
            spread  = (100 - profile.get('consistency', 75)) * 0.08
            best    = max(base + random.gauss(0, spread) for _ in range(3))
            results.append({
                'name': name, 'car': opp.get('car', ''),
                'team': opp.get('team', ''), 'is_player': False, 'pace_score': best,
            })

        # Player pace: relative to field average, scaled by adaptive AI level
        field_avg   = sum(r['pace_score'] for r in results) / len(results) if results else 0
        player_pace = field_avg + (ai_lvl - 80) * 0.15 + random.gauss(0, 1.5)
        results.append({
            'name': 'PLAYER', 'car': '', 'team': '', 'is_player': True, 'pace_score': player_pace,
        })

        results.sort(key=lambda x: x['pace_score'], reverse=True)
        for i, r in enumerate(results):
            r['position'] = i + 1
        return results

    def simulate_practice(self, opponents, ai_lvl, career_data=None):
        """Simulate free practice for all opponents + player.

        Longer runs (5 stints), more variance than qualifying. Uses race skill
        as base (not quali_pace) since FP reflects long-run pace.

        Returns list sorted P1→last:
            [{'name', 'car', 'team', 'is_player', 'pace_score', 'position'}, ...]
        """
        player_team = (career_data or {}).get('team')
        results = []
        for opp in opponents[:19]:
            if player_team and opp.get('team') == player_team:
                continue  # player fills this slot — skip the AI stand-in
            name    = opp.get('driver_name') or ''
            profile = self.get_driver_profile(name, career_data=career_data)
            base    = opp.get('performance', 0) + (profile.get('skill', 80) - 80) * 0.3
            spread  = (100 - profile.get('consistency', 75)) * 0.15
            best    = max(base + random.gauss(0, spread) for _ in range(5))
            results.append({
                'name': name, 'car': opp.get('car', ''),
                'team': opp.get('team', ''), 'is_player': False, 'pace_score': best,
            })

        field_avg   = sum(r['pace_score'] for r in results) / len(results) if results else 0
        player_pace = field_avg + (ai_lvl - 80) * 0.12 + random.gauss(0, 2.0)
        results.append({
            'name': 'PLAYER', 'car': '', 'team': '', 'is_player': True, 'pace_score': player_pace,
        })

        results.sort(key=lambda x: x['pace_score'], reverse=True)
        for i, r in enumerate(results):
            r['position'] = i + 1
        return results

    # ------------------------------------------------------------------
    # Standings — deterministic AI, real player points
    # ------------------------------------------------------------------

    def _get_name_mode(self, career_data):
        cs = (career_data or {}).get('career_settings') or {}
        mode = str(cs.get('name_mode', 'curated')).strip().lower()
        return mode if mode in {'curated', 'procedural'} else 'curated'

    def _get_procedural_driver_name(self, global_slot, season, career_seed):
        cache_key = (season, career_seed)
        pool = self._procedural_name_cache.get(cache_key)
        if pool is None:
            first_names = sorted({name.split(' ', 1)[0] for name in self.DRIVER_NAMES if ' ' in name})
            last_names = sorted({name.split(' ', 1)[1] for name in self.DRIVER_NAMES if ' ' in name})
            seed = int(hashlib.md5(
                f"procedural_names|{season}|{career_seed}".encode()
            ).hexdigest()[:8], 16)
            rng = random.Random(seed)
            pairs = [f"{first} {last}" for first in first_names for last in last_names]
            rng.shuffle(pairs)
            pool = pairs
            self._procedural_name_cache[cache_key] = pool
        return pool[global_slot % len(pool)]

    def _get_driver_name(self, global_slot, season, career_seed=0, name_mode='curated'):
        """Return a globally unique driver name for the given slot and season.
        Uses a single season-seeded shuffle of the full name pool so that each
        slot index maps to a distinct name across all tiers simultaneously."""
        if name_mode == 'procedural':
            return self._get_procedural_driver_name(global_slot, season, career_seed)
        seed = int(hashlib.md5(
            f"global_drivers|{season}|{career_seed}".encode()
        ).hexdigest()[:8], 16)
        rng  = random.Random(seed)
        pool = list(self.DRIVER_NAMES)
        rng.shuffle(pool)
        return pool[global_slot % len(pool)]

    def _get_driver_split(self, team_name, tier_key, season):
        """Deterministic primary-driver share of team points (0.50–0.65)."""
        seed = int(hashlib.md5(
            f"split|{team_name}|{tier_key}|{season}".encode()
        ).hexdigest()[:8], 16)
        rng = random.Random(seed)
        return 0.50 + rng.random() * 0.15

    def _is_car_usable(self, car, ac_path):
        """Return True if the car folder has data/ or data.acd (i.e. is not empty/missing)."""
        if not car or not ac_path:
            return True  # no AC path → don't filter; preflight will warn later
        car_path = os.path.join(ac_path, 'content', 'cars', car)
        return (
            os.path.isdir(os.path.join(car_path, 'data')) or
            os.path.isfile(os.path.join(car_path, 'data.acd'))
        )

    def generate_standings(self, tier_info, career_data, tier_key=None):
        """Build driver championship standings.

        MX5 Cup is a single-driver series (1 entry per team).
        GT4 / GT3 / WEC have 2 championship drivers per team.
        Names are globally unique across all 4 tiers (season-seeded global shuffle).
        Teams whose car folder is empty or missing are silently excluded.
        """
        races_done  = career_data.get('races_completed', 0)
        player_pts  = career_data.get('points', 0)
        player_team = career_data.get('team')
        season      = career_data.get('season', 1)
        tier_index  = career_data.get('tier', 0)
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode   = self._get_name_mode(career_data)

        if tier_key is None:
            tier_key = self.tiers[tier_index]

        # Filter teams whose car folder is empty / missing data
        ac_path     = self.config.get('paths', {}).get('ac_install', '')
        valid_teams = [t for t in tier_info['teams']
                       if self._is_car_usable(t.get('car', ''), ac_path)]
        team_count  = len(valid_teams)

        dpt    = self.DRIVERS_PER_TEAM.get(tier_key, 1)   # drivers per team
        offset = self.TIER_SLOT_OFFSET.get(tier_key, 0)   # global slot start

        entries = []
        for i, team in enumerate(valid_teams):
            is_player_team = (team['name'] == player_team)
            slot1 = offset + i * dpt

            if is_player_team:
                pts1  = player_pts
                name1 = career_data.get('driver_name') or 'Player'
            else:
                pts1  = self._calc_ai_points(team, season, tier_index, races_done, team_count)
                name1 = self._get_driver_name(slot1, season, career_seed, name_mode)

            if dpt == 1:
                # Single-driver entry (MX5 Cup)
                entries.append({
                    'team':       team['name'],
                    'driver':     name1,
                    'driver2':    None,
                    'car':        team['car'],
                    'points':     pts1,
                    'races':      races_done,
                    'is_player':  is_player_team,
                    'is_primary': True,
                    'tier_level': team.get('tier', 'customer'),
                })
            else:
                # Two drivers per team (GT4 / GT3 / WEC)
                slot2 = slot1 + 1
                name2 = self._get_driver_name(slot2, season, career_seed, name_mode)

                # Co-driver uses the same team performance but a slightly different seed
                codriver_team = dict(team)
                codriver_team['name'] = team['name'] + '_codriver'
                pts2 = self._calc_ai_points(
                    codriver_team, season, tier_index, races_done, team_count
                )

                # Primary driver entry
                entries.append({
                    'team':       team['name'],
                    'driver':     name1,
                    'driver2':    name2,
                    'car':        team['car'],
                    'points':     pts1,
                    'races':      races_done,
                    'is_player':  is_player_team,
                    'is_primary': True,
                    'tier_level': team.get('tier', 'customer'),
                })
                # Co-driver entry
                entries.append({
                    'team':       team['name'],
                    'driver':     name2,
                    'driver2':    name1,
                    'car':        team['car'],
                    'points':     pts2,
                    'races':      races_done,
                    'is_player':  False,
                    'is_primary': False,
                    'tier_level': team.get('tier', 'customer'),
                })

        entries.sort(key=lambda x: x['points'], reverse=True)
        leader = entries[0]['points'] if entries else 0
        ai_skin = 1
        for i, s in enumerate(entries):
            s['position'] = i + 1
            s['gap']      = leader - s['points']
            if s['is_player']:
                s['skin_index'] = 0
            else:
                s['skin_index'] = ai_skin
                ai_skin += 1

        return entries

    def generate_team_standings_from_drivers(self, driver_entries):
        """Aggregate driver entries into team championship (1 row per team, summed points)."""
        teams_order = []
        seen = {}
        for entry in driver_entries:
            tn = entry['team']
            if tn not in seen:
                teams_order.append(tn)
                seen[tn] = {
                    'team':       tn,
                    'car':        entry['car'],
                    'points':     0,
                    'races':      entry['races'],
                    'is_player':  False,
                    'tier_level': entry['tier_level'],
                    '_drivers':   [],
                }
            seen[tn]['points'] += entry['points']
            seen[tn]['_drivers'].append((entry.get('is_primary', True), entry['driver']))
            if entry.get('is_player'):
                seen[tn]['is_player'] = True

        team_list = []
        for tn in teams_order:
            t = seen[tn]
            # Sort so primary driver (is_primary=True) is first
            drivers = sorted(t.pop('_drivers'), key=lambda x: (0 if x[0] else 1))
            t['driver']  = drivers[0][1] if drivers else ''
            t['driver2'] = drivers[1][1] if len(drivers) > 1 else None
            team_list.append(t)

        team_list.sort(key=lambda x: x['points'], reverse=True)
        leader = team_list[0]['points'] if team_list else 0
        for i, t in enumerate(team_list):
            t['position'] = i + 1
            t['gap']      = leader - t['points']
        return team_list

    def generate_all_standings(self, career_data):
        """Return standings for all 4 tiers simultaneously.
        Each tier returns {'drivers': [...], 'teams': [...]}.
        Player appears only in their own tier; other tiers show pure AI with
        standings proportional to the player's season progress."""
        result       = {}
        player_tier  = career_data.get('tier', 0)
        player_races = career_data.get('races_completed', 0)
        player_total = self.get_tier_races(career_data)
        fraction     = player_races / player_total if player_total > 0 else 1.0
        cs           = career_data.get('career_settings') or {}

        for idx, tk in enumerate(self.tiers):
            tier_info = self.config['tiers'][tk]
            if idx == player_tier:
                sim = career_data
            else:
                other_tracks = (cs.get('custom_tracks') or {}).get(tk) or tier_info['tracks']
                ai_races     = round(fraction * len(other_tracks))
                sim = {
                    'tier':            idx,
                    'season':          career_data.get('season', 1),
                    'team':            None,
                    'races_completed': ai_races,
                    'points':          0,
                    'driver_name':     '',
                    'driver_progress': career_data.get('driver_progress', {}),
                }
            drivers = self.generate_standings(tier_info, sim, tier_key=tk)
            teams   = self.generate_team_standings_from_drivers(drivers)
            result[tk] = {'drivers': drivers, 'teams': teams}
        return result

    def pick_rival(self, tier_key, season, career_data=None):
        """Pick the AI driver in tier_key whose skill is closest to 82.
        Called at new career start and on every contract acceptance (new season/tier).
        Returns a driver name string, or None if no drivers found.
        """
        tier_info = self.config['tiers'].get(tier_key)
        if not tier_info:
            return None
        offset    = self.TIER_SLOT_OFFSET.get(tier_key, 0)
        dpt       = self.DRIVERS_PER_TEAM.get(tier_key, 1)
        career_seed = int((career_data or {}).get('driver_seed') or 0)
        name_mode = self._get_name_mode(career_data)
        best_name = None
        best_diff = 999
        for i in range(len(tier_info['teams'])):
            slot    = offset + i * dpt
            name    = self._get_driver_name(slot, season, career_seed, name_mode)
            profile = self.get_driver_profile(name, career_data=career_data)
            diff    = abs(profile.get('skill', 80) - 82)
            if diff < best_diff:
                best_diff = diff
                best_name = name
        return best_name

    def _calc_ai_points(self, team, season, tier_index, races_done, team_count):
        """
        Deterministic per-race AI points using MD5-seeded RNG.
        Same inputs → same output every time.
        """
        if races_done == 0:
            return 0

        pts_table = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        perf      = team.get('performance', 0)   # −1.5 (slow) … +0.5 (fast)
        total     = 0

        for race_num in range(races_done):
            seed_str = f"{team['name']}|{season}|{tier_index}|{race_num}"
            seed     = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
            rng      = random.Random(seed)

            # Map performance to expected finishing position
            # perf 0.5  → position ≈ 1–3   (top)
            # perf -1.5 → position ≈ near back
            norm     = max(0.0, min(1.0, (0.5 - perf) / 2.0))
            base_pos = max(1, int(norm * team_count) + 1)

            # Add realistic race-to-race noise (±3 positions)
            pos = base_pos + rng.randint(-3, 3)
            pos = max(1, min(team_count, pos))

            total += pts_table[pos - 1] if pos <= 10 else 0

        return total

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    def generate_contract_offers(self, player_position, next_tier, config,
                                 current_tier=0, team_count=20):
        """Generate contract offers based on championship finish.

        Bottom 3 finishers get degradation risk: only the worst seat in the
        current tier or (if not already in the lowest tier) offers from the
        tier below.  Champion always gets promoted; top-3 get scouted by
        higher-tier teams.
        """
        degradation_risk = (player_position >= team_count - 2)

        # Career complete: only when NOT in degradation risk and already at top tier.
        # Degradation risk takes priority — even WEC last-place finishers drop to GT3.
        if not degradation_risk and next_tier >= len(self.tiers):
            return [{'message': 'Congratulations! Career complete!', 'complete': True}]

        if degradation_risk:
            offers = []
            current_tier_info = config['tiers'][self.tiers[current_tier]]

            # Worst customer seat in current tier (stay / same level)
            customers = [t for t in current_tier_info['teams']
                         if t.get('tier', 'customer') == 'customer']
            customers.sort(key=lambda t: t.get('performance', 0))
            if customers:
                team = customers[0]
                offers.append({
                    'id':               f"contract_deg_0_{int(datetime.now().timestamp())}",
                    'team_name':        team['name'],
                    'car':              team['car'],
                    'tier_name':        self.tier_names[self.tiers[current_tier]],
                    'tier_level':       'customer',
                    'target_tier':      current_tier,          # stay in same tier
                    'move':             'stay',
                    'degradation_risk': True,
                    'description':      (
                        f"Your season results were poor. "
                        f"{team['name']} offers you a chance to stay in "
                        f"{self.tier_names[self.tiers[current_tier]]}."
                    ),
                })

            # Offer(s) from lower tier (relegation — only if not already at bottom)
            if current_tier > 0:
                lower_tier_key  = self.tiers[current_tier - 1]
                lower_tier_info = config['tiers'][lower_tier_key]
                lower_teams     = [t for t in lower_tier_info['teams']
                                   if t.get('tier', 'customer') in ('factory', 'semi')]
                lower_teams.sort(key=lambda t: t.get('performance', 0), reverse=True)
                for j, team in enumerate(lower_teams[:2]):
                    offers.append({
                        'id':               f"contract_deg_{j+1}_{int(datetime.now().timestamp())}",
                        'team_name':        team['name'],
                        'car':              team['car'],
                        'tier_name':        self.tier_names[lower_tier_key],
                        'tier_level':       team.get('tier', 'semi'),
                        'target_tier':      current_tier - 1,  # drop one tier
                        'move':             'relegation',
                        'degradation_risk': True,
                        'description':      (
                            f"{team['name']} in {self.tier_names[lower_tier_key]} "
                            f"is interested in signing you."
                        ),
                    })
            return offers

        # Normal promotion path
        tier_info = config['tiers'][self.tiers[next_tier]]

        if player_position == 1:
            offer_count = config.get('contracts', {}).get('champion_offers', 4)
            tier_filter = ['factory', 'semi']
        elif player_position <= 3:
            offer_count = config.get('contracts', {}).get('top5_offers', 3)
            tier_filter = ['factory', 'semi']
        elif player_position <= 5:
            offer_count = config.get('contracts', {}).get('top5_offers', 3)
            tier_filter = ['semi', 'customer']
        elif player_position <= 10:
            offer_count = config.get('contracts', {}).get('top10_offers', 2)
            tier_filter = ['customer']
        else:
            offer_count = 1
            tier_filter = ['customer']

        available = [
            t for t in tier_info['teams']
            if t.get('tier', 'customer') in tier_filter
        ]

        selected = random.sample(available, min(offer_count, len(available)))

        offers = []
        for i, team in enumerate(selected):
            offers.append({
                'id':               f"contract_{i}_{int(datetime.now().timestamp())}",
                'team_name':        team['name'],
                'car':              team['car'],
                'tier_name':        self.tier_names[self.tiers[next_tier]],
                'tier_level':       team.get('tier', 'customer'),
                'target_tier':      next_tier,                 # promote to next tier
                'move':             'promotion',
                'degradation_risk': False,
                'description':      (
                    f"Join {team['name']} for the "
                    f"{self.tier_names[self.tiers[next_tier]]} season"
                ),
            })

        return offers

    # ------------------------------------------------------------------
    # AC launch
    # ------------------------------------------------------------------

    def _write_simulated_quali_result(self, grid, race_data):
        """Write a fake qualifying result JSON to the AC results folder.

        AC reads the newest QUALIFY-type result file to determine starting grid.
        Without this, Race Only mode always puts the player last (no qualifying data).
        By writing this file before launching the race, AC places every driver at
        their simulated qualifying position.

        grid:      sorted list from simulate_qualifying() — P1 first.
        race_data: dict with 'driver_name', 'car', 'track', 'config_track'.
        """
        if not grid:
            return

        results_dir = get_ac_docs_path('results')
        os.makedirs(results_dir, exist_ok=True)

        driver_name  = race_data.get('driver_name', 'Player')
        car_model    = race_data.get('car', '')
        track_raw    = race_data.get('track', '')
        track_folder = track_raw.split('/')[0] if '/' in track_raw else track_raw
        config_track = track_raw.split('/')[1] if '/' in track_raw else race_data.get('config_track', '')

        # Lap times: P1 gets BASE_LAP_MS, each subsequent position is GAP_PER_POS ms slower.
        # Absolute values don't matter — AC sorts ascending; only the order counts.
        BASE_LAP_MS = 84000   # 1m24s — plausible for any career track
        GAP_PER_POS = 400     # ms per qualifying position

        result_entries = []
        for i, entry in enumerate(grid):
            is_player = entry.get('is_player', False)
            name = driver_name if is_player else entry.get('name', f'Driver_{i+1}')
            car  = car_model   if is_player else entry.get('car', car_model)
            result_entries.append({
                "DriverName": name,
                "CarModel":   car,
                "BestLap":    BASE_LAP_MS + i * GAP_PER_POS,
                "TotalTime":  BASE_LAP_MS + i * GAP_PER_POS,
                "BallastKG":  0,
            })

        quali_json = {
            "Type":         "QUALIFY",
            "TrackName":    track_folder,
            "TrackConfig":  config_track,
            "Description":  "Simulated qualifying — AC Career GT Edition",
            "Date":         int(datetime.now().timestamp()),
            "DurationSecs": 600,
            "RaceLaps":     0,
            "Result":       result_entries,
            "Laps":         [],
            "Events":       [],
        }

        fname = datetime.now().strftime('%Y_%m_%d_%H_%M_%S') + '.json'
        fpath = os.path.join(results_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(quali_json, f, indent=2)
        print(f"Wrote simulated qualifying result: {fpath}")

    def _get_ac_docs_cfg(self):
        """Return path to AC's config folder where AC actually reads race.ini.
        Windows: ~/Documents/Assetto Corsa/cfg
        Linux:   Proton compat-data path/.../Documents/Assetto Corsa/cfg
        """
        return get_ac_docs_path("cfg")

    def launch_ac_race(self, race_config, config, mode='race_only', career_data=None,
                       session_type=None, grid=None):
        """Launch Assetto Corsa with race configuration.

        mode:         'race_only' (default) | 'full_weekend'
        session_type: 'practice' | 'qualifying' | 'race' — for split weekend sessions.
        grid:         Pre-sorted car list from simulate_qualifying() or AC quali results.
        """
        ac_path = config['paths']['ac_install']

        if not os.path.exists(ac_path):
            print(f"AC not found at {ac_path}")
            return False

        # AC reads config from Documents\Assetto Corsa\cfg — NOT the install folder
        docs_cfg = self._get_ac_docs_cfg()
        print(f"Writing config to: {docs_cfg}")

        # 1. Write race.ini to Documents (where AC actually reads it)
        race_cfg_path = os.path.join(docs_cfg, 'race.ini')
        self._write_race_config(race_cfg_path, race_config, ac_path, mode=mode,
                                career_data=career_data, session_type=session_type, grid=grid)

        # 1b. For race sessions with a simulated grid, write a qualifying result JSON
        #     so AC uses the correct starting grid order instead of defaulting to last.
        if grid and (session_type == 'race' or mode == 'race_only'):
            self._write_simulated_quali_result(grid, race_config)

        # 2. Patch launcher.ini in Documents so AC starts in race mode
        launcher_path = os.path.join(docs_cfg, 'launcher.ini')
        self._patch_launcher_ini(launcher_path, race_config)

        # 3. Launch AC — method differs by OS
        try:
            if is_linux():
                # Linux: AC runs under Steam Proton; launch via Steam applaunch so
                # Proton environment, version pinning, and launch options are respected.
                subprocess.Popen(['steam', '-applaunch', '244210'])
            else:
                ac_exe = os.path.join(ac_path, 'acs.exe')
                subprocess.Popen(ac_exe, cwd=ac_path)
            return True
        except Exception as e:
            print(f"Failed to launch AC: {e}")
            return False

    def _patch_launcher_ini(self, launcher_path, race_config):
        """Patch DRIVE=race and TRACK in launcher.ini using raw line replacement.
        AC requires KEY=VALUE with NO spaces around = (strict format)."""
        try:
            track_folder = race_config['track'].split('/')[0]

            with open(launcher_path, 'r') as f:
                lines = f.readlines()

            patched_drive = False
            patched_track = False
            new_lines = []

            for line in lines:
                key = line.split('=')[0].strip().upper() if '=' in line else ''
                if key == 'DRIVE':
                    new_lines.append('DRIVE=race\n')
                    patched_drive = True
                elif key == 'TRACK':
                    new_lines.append(f'TRACK={track_folder}\n')
                    patched_track = True
                else:
                    new_lines.append(line)

            # If keys not found, insert after [SAVED] header
            if not patched_drive or not patched_track:
                result = []
                for line in new_lines:
                    result.append(line)
                    if line.strip().upper() == '[SAVED]':
                        if not patched_drive:
                            result.append('DRIVE=race\n')
                        if not patched_track:
                            result.append(f'TRACK={track_folder}\n')
                new_lines = result

            with open(launcher_path, 'w') as f:
                f.writelines(new_lines)

            print(f"launcher.ini patched: DRIVE=race TRACK={track_folder}")
        except Exception as e:
            print(f"Warning: could not patch launcher.ini: {e}")

    def _get_car_skin(self, car, ac_path, index=0):
        """Return skin at the given index for a car (wraps around if fewer skins).
        Use index=0 for player, index=1..N for AI cars so each gets a distinct livery."""
        skins_dir = os.path.join(ac_path, 'content', 'cars', car, 'skins')
        try:
            skins = sorted(os.listdir(skins_dir))
            return skins[index % len(skins)] if skins else ''
        except Exception:
            return ''

    def _write_race_config(self, config_path, race_data, ac_path='', mode='race_only',
                           career_data=None, session_type=None, grid=None):
        """Write AC race.ini in the format AC expects (Documents/Assetto Corsa/cfg/race.ini).

        mode:         'race_only' (default) | 'full_weekend' (practice + quali + race in one go)
        session_type: 'practice' | 'qualifying' | 'race' — single session for split weekend.
                      When set, overrides mode for session content and AI level calculation.
        grid:         Sorted list from simulate_qualifying() or actual quali results.
                      When provided, cars are written in grid order (player at correct position).
        """
        driver           = race_data.get('driver_name', 'Player')
        car              = race_data['car']
        laps             = race_data['laps']
        ai_lvl           = int(race_data['ai_difficulty'])
        opponents        = race_data.get('opponents', [])
        practice_minutes = race_data.get('practice_minutes', 10)
        quali_minutes    = race_data.get('quali_minutes', 10)
        weather          = race_data.get('weather', '3_clear')

        # Limit to 19 AI cars (20 total including player)
        ai_cars = opponents[:19]
        # When grid is provided its length is exact; otherwise ai_cars already contains
        # the right number of slots (player replaces their own team's AI entry, so the
        # total stays len(ai_cars), not len(ai_cars)+1).
        total_cars = len(grid) if grid else len(ai_cars)

        # Track can be "folder/layout" or just "folder"
        track_raw    = race_data['track']
        parts        = track_raw.split('/')
        track_folder = parts[0]
        config_track = parts[1] if len(parts) > 1 else ''

        # Player gets skin index 0; AI cars get 1, 2, 3… so each has a distinct livery
        skin = self._get_car_skin(car, ac_path, index=0) if ac_path else ''

        lines = []

        # [RACE] — main race block
        lines += [
            "[RACE]",
            f"TRACK={track_folder}",
            f"CONFIG_TRACK={config_track}",
            f"MODEL={car}",
            f"MODEL_CONFIG=",
            f"SKIN={skin}",
            f"PENALTIES=1",
            f"FIXED_SETUP=0",
            f"DRIFT_MODE=0",
            f"RACE_LAPS={laps}",
            f"CARS={total_cars}",
            f"AI_LEVEL={ai_lvl}",
            f"JUMP_START_PENALTY=0",
            f"WEATHER_0={weather}",
        ]
        if race_data.get('sun_angle') is not None:
            lines.append(f"SUN_ANGLE={race_data['sun_angle']}")
        if race_data.get('time_of_day_mult') is not None:
            lines.append(f"TIME_OF_DAY_MULT={race_data['time_of_day_mult']}")
        lines.append("")

        # [DRIVE] — player config
        # AI_LEVEL must be empty — a non-empty value tells AC to control this car as AI.
        lines += [
            "[DRIVE]",
            f"MODEL={car}",
            f"SKIN={skin}",
            f"MODEL_CONFIG=",
            f"AI_LEVEL=",
            f"AI_AGGRESSION=0",
            f"SETUP=",
            f"FIXED_SETUP=0",
            f"VIRTUAL_MIRROR=0",
            f"DRIVER_NAME={driver}",
            f"NATIONALITY=",
            "",
        ]

        # [HEADER] — AC uses VERSION=2 to signal post-qualifying grid format.
        # Without this, AC may misread the file and misidentify the player car.
        lines += [
            "[HEADER]",
            "VERSION=2",
            "",
        ]

        # Sessions — single session (split weekend) or combined (full_weekend / race_only)
        if session_type == 'practice':
            lines += [
                "[SESSION_0]",
                "NAME=PRACTICE",
                "TYPE=1",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={practice_minutes}",
                "LAPS=0",
                "",
            ]
        elif session_type == 'qualifying':
            lines += [
                "[SESSION_0]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={quali_minutes}",
                "LAPS=0",
                "",
            ]
        elif session_type == 'race':
            # Add a 0-minute QUALIFY session before RACE so AC reads the
            # simulated qualifying JSON to order the starting grid.
            # Without SESSION TYPE=2, AC ignores any qualifying result file
            # and falls back to default order (player last).
            lines += [
                "[SESSION_0]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                "DURATION_MINUTES=0",
                "LAPS=0",
                "",
                "[SESSION_1]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]
        elif mode == 'full_weekend':
            lines += [
                "[SESSION_0]",
                "NAME=PRACTICE",
                "TYPE=1",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={practice_minutes}",
                "LAPS=0",
                "",
                "[SESSION_1]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                f"DURATION_MINUTES={quali_minutes}",
                "LAPS=0",
                "",
                "[SESSION_2]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]
        else:
            lines += [
                "[SESSION_0]",
                "NAME=QUALIFY",
                "TYPE=2",
                "SPAWN_SET=PIT",
                "DURATION_MINUTES=0",
                "LAPS=0",
                "",
                "[SESSION_1]",
                "NAME=RACE",
                "TYPE=3",
                "SPAWN_SET=START",
                f"LAPS={laps}",
                "DURATION_MINUTES=0",
                "",
            ]

        # [GROOVE]
        lines += [
            "[GROOVE]",
            "VIRTUAL_LAPS=10",
            "MAX_LAPS=30",
            "STARTING_LAPS=0",
            "",
        ]

        # Wet weather detection — used for per-driver wet_skill AI adjustment
        WET_PRESETS = {'rainy', 'heavy_rain', 'wet', 'light_rain', 'drizzle', 'stormy', 'overcast_wet'}
        is_wet = weather.lower() in WET_PRESETS

        # Night/endurance detection — used for per-driver night_skill AI adjustment
        sun_angle  = race_data.get('sun_angle')
        time_mult  = race_data.get('time_of_day_mult') or 1
        if time_mult > 1:
            night_weight = 0.5   # endurance: ~half the race in darkness
        elif sun_angle is not None and sun_angle < -30:
            night_weight = 1.0   # explicit night race
        else:
            night_weight = 0.0

        # Success ballast: car model is the team differentiator; ballast only penalises recent winners.
        # Count P1 finishes in the last 3 races — each win adds 5 kg (max 15 kg).
        recent = (career_data or {}).get('race_results', [])[-3:]
        player_ballast = sum(5 for r in recent if r.get('position') == 1)

        # Base variance from config (used to scale per-driver consistency)
        base_variance = self.config.get('difficulty', {}).get('ai_level_variance', 1.5)

        # Determine which skill attribute drives AI level for this session
        # qualifying → quali_pace only; full_weekend → blend; everything else → race skill
        if session_type == 'qualifying':
            ai_skill_mode = 'qualifying'
        elif mode == 'full_weekend':
            ai_skill_mode = 'blend'
        else:
            ai_skill_mode = 'race'

        def _ai_level_for(profile_):
            """Compute a single AI level value for one driver."""
            if ai_skill_mode == 'qualifying':
                eff = float(profile_.get('quali_pace', 75))
            elif ai_skill_mode == 'blend':
                eff = (profile_['skill'] + profile_.get('quali_pace', 75)) / 2
            else:
                eff = float(profile_['skill'])
            s_off = int((eff - 80) * 0.2)
            w_adj = round((profile_.get('wet_skill', 60) - 50) * 0.08) if is_wet else 0
            n_adj = round((profile_.get('night_skill', 60) - 60) * 0.12 * night_weight)
            cons  = profile_.get('consistency', 75)
            dvar  = min(base_variance * (1 + (50 - cons) / 50), 1.5)
            v_adj = random.uniform(-dvar, dvar)
            return max(50, min(100, int(ai_lvl + s_off + w_adj + n_adj + v_adj)))

        # Build ordered car list: grid order if provided, otherwise player P1 then AI.
        # grid entries: {'name', 'car', 'team', 'is_player', ...} sorted P1→last.
        # The player occupies one team slot, so that team must NOT also get an AI entry —
        # otherwise CARS count and actual CAR blocks diverge, producing a ghost "No name" car.
        opp_by_name  = {(opp.get('driver_name') or ''): opp for opp in ai_cars}
        player_team  = (career_data or {}).get('team')

        if grid:
            car_entries = []
            for g in grid:
                if g.get('is_player'):
                    car_entries.append({'type': 'player'})
                else:
                    opp = opp_by_name.get(g['name'], {'car': g.get('car', car), 'driver_name': g['name']})
                    car_entries.append({'type': 'ai', 'opp': opp})
        else:
            # Skip the AI stand-in for the player's own team slot (ghost driver fix).
            car_entries = [{'type': 'player'}] + [
                {'type': 'ai', 'opp': opp} for opp in ai_cars
                if not (player_team and opp.get('team') == player_team)
            ]

        # AC identifies the player via CAR_0 with MODEL=- (confirmed from AC's own race.ini format).
        # Ensure the player entry is always at index 0, AI cars fill indices 1..N in grid order.
        # In Race Only mode this means the player starts last (no qualifying data for AC to use).
        # In Full Weekend mode, AC reorders the grid from qualifying results automatically.
        player_idx = next((i for i, e in enumerate(car_entries) if e['type'] == 'player'), None)
        if player_idx is not None and player_idx != 0:
            player_entry = car_entries.pop(player_idx)
            car_entries.insert(0, player_entry)

        # Write [CAR_N] blocks in grid order
        # AI skins start at index 1 to reserve index 0 (00_official) exclusively for the player.
        # Using index=i would give CAR_0 skin index 0, colliding with the player livery and
        # causing AC to misidentify which car is the player.
        ai_skin_counter = 1
        for i, entry in enumerate(car_entries):
            if entry['type'] == 'player':
                # AC identifies the player slot via MODEL=- (a literal dash).
                # This is the format AC itself writes after a qualifying session.
                # AI_LEVEL and AI_AGGRESSION are omitted entirely for the player block.
                lines += [
                    f"[CAR_{i}]",
                    f"SETUP=",
                    f"SKIN={skin}",
                    f"MODEL=-",
                    f"MODEL_CONFIG=",
                    f"BALLAST={player_ballast}",
                    f"RESTRICTOR=0",
                    f"DRIVER_NAME={driver}",
                    f"NATIONALITY=",
                    "",
                ]
            else:
                opp      = entry['opp']
                opp_car  = opp.get('car', car)
                opp_skin = self._get_car_skin(opp_car, ac_path, index=ai_skin_counter) if ac_path else ''
                ai_skin_counter += 1
                name     = opp.get('driver_name') or self.DRIVER_NAMES[i % len(self.DRIVER_NAMES)]
                # Prevent name collision with player: if an AI driver shares the player's
                # career name, read_race_result() would return the AI's result instead of
                # the player's actual result (the first match wins).
                if name.lower() == driver.lower():
                    name = name + ' II'
                profile  = self.get_driver_profile(name, career_data=career_data)
                nation   = profile['nationality']

                opp_ai_level  = _ai_level_for(profile)
                opp_aggression = profile['aggression']
                consistency    = profile.get('consistency', 75)
                if consistency < 50:
                    opp_aggression = min(100, opp_aggression + int((50 - consistency) * 0.3))

                lines += [
                    f"[CAR_{i}]",
                    f"MODEL={opp_car}",
                    f"SKIN={opp_skin}",
                    f"MODEL_CONFIG=",
                    f"DRIVER_NAME={name}",
                    f"NATION_CODE={nation}",
                    f"AI_LEVEL={opp_ai_level}",
                    f"AI_AGGRESSION={opp_aggression}",
                    f"SETUP=",
                    f"BALLAST=0",
                    f"RESTRICTOR=0",
                    "",
                ]

        content = "\n".join(lines)

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(content)

        print(f"race.ini written: {track_folder}/{config_track} | car={car} | laps={laps} | AI cars={len(ai_cars)}")


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    with open('config.json', 'r') as f:
        cfg = json.load(f)

    mgr      = CareerManager(cfg)
    tier_info = mgr.get_tier_info(0)
    fake_career = {
        'tier': 0, 'season': 1, 'team': 'Mazda Academy',
        'car': 'ks_mazda_mx5_cup', 'races_completed': 3,
        'points': 43, 'driver_name': 'Test Driver'
    }
    standings = mgr.generate_standings(tier_info, fake_career)
    for s in standings[:5]:
        print(s)
