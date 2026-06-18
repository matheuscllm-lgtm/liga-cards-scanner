"""Normalizacao de nomes de cards e sets para matching robusto.

Aplica:
- lowercase
- remocao de acentos (NFKD)
- colapso de espacos em branco
- aliases comuns de sets (codigos curtos -> nome canonico)
- normalizacao de variantes (V-MAX/VMAX, V-STAR/VSTAR)
"""
from __future__ import annotations

import re
import unicodedata

# Mapa de codigos/aliases comuns -> nome canonico (em minusculas).
# Ja em lowercase e sem acentos. Expandir conforme novos sets.
SET_ALIASES: dict[str, str] = {
    "obf": "obsidian flames",
    "lor": "lost origin",
    "stb": "silver tempest",
    "fst": "fusion strike",
    "viv": "vivid voltage",
    "pal": "paldea evolved",
    "sv": "scarlet & violet",
    "s&v": "scarlet & violet",
    "svi": "scarlet & violet",
    # Codigos reais de sets SV/SWSH vistos na Liga (expansao 2026-06-18).
    "pre": "prismatic evolutions",
    "ssp": "surging sparks",
    "jtg": "journey together",
    "twm": "twilight masquerade",
    "scr": "stellar crown",
    "sfa": "shrouded fable",
    "paf": "paldean fates",
    "par": "paradox rift",
    "tef": "temporal forces",
    "151": "scarlet & violet 151",
    "mew": "scarlet & violet 151",
}


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = _strip_accents(s).lower()
    # Remove pontuacao (pontos, apostrofos, hifens, virgulas...) que so atrapalha
    # o matching: "Mr. Mime" == "Mr Mime", "Professor's Research" == "Professors
    # Research". Mantem o "&" porque ele faz parte de nomes de set canonicos
    # ("Scarlet & Violet") e dos aliases (s&v) — tira-lo dessincronizaria o alias
    # do nome completo.
    s = re.sub(r"[^\w\s&]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_card_name(name: str) -> str:
    s = normalize_text(name)
    # Variantes comuns escritas com hifen ou espaco
    s = s.replace("v-max", "vmax").replace("v max", "vmax")
    s = s.replace("v-star", "vstar").replace("v star", "vstar")
    s = s.replace("v-union", "vunion").replace("v union", "vunion")
    return re.sub(r"\s+", " ", s).strip()


def normalize_set_name(set_name: str) -> str:
    s = normalize_text(set_name)
    return SET_ALIASES.get(s, s)
