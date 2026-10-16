"""Plain-language topic guide for Constitution search.

People rarely ask in the Constitution's own words: they ask whether police can
search a phone, not about "telegraphic communications". This module maps
everyday phrasing to section numbers so retrieval can rank the right provision
even when dense or keyword search misses it. It only steers ranking; every
returned provision is still loaded from the published release.

Section titles come from the source PDF's "Arrangement of sections" and are
navigation aids, not legal text.
"""

import itertools
import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_TITLES_PATH = Path(__file__).parent / "data" / "constitution-1999-section-titles.json"
_SECTION_IN_PATH = re.compile(r"\.section(\d+[a-z]?)(?=\.|$)")
_CHAPTER_IN_PATH = re.compile(r"\.chapter(\d+)(?=\.|$)")
_TOKEN = re.compile(r"[a-z0-9]+")
# Asking what to do about a wrong is asking about enforcement (Section 46),
# even though the words themselves are all filler.
_REMEDY_INTENT = re.compile(
    r"\bwhat (?:can|should|do) (?:i|we|you|one) do\b"
    r"|\bwhere (?:can|do|should) (?:i|we) (?:go|report|complain)\b"
    r"|\bhow (?:can|do|should) (?:i|we) (?:complain|report|sue|challenge|seek)\b",
    re.I,
)

# Function words and conversational filler, including common Nigerian Pidgin.
# Topic words such as "law", "state" and "nigeria" stay meaningful.
STOPWORDS = frozenset(
    """
    a an the of to in on at for by with from about into onto as than then there
    here is are was were be been being am do does did done can could may might
    must shall should will would i me my mine myself we us our you your yours he
    him his she her it its they them their this that these those what which who
    whom whose when where why how and or but if so any some all not no yes have
    has had get gets got say says said tell talk talks wetin dey abeg una wey na
    oga sir madam please pls kindly just also only even still really very much
    mean means meaning
    """.split()
)
# Irregular forms the suffix rules below cannot reach.
_LEMMAS = {
    "sued": "sue",
    "suing": "sue",
    "sues": "sue",
    "children": "child",
    "women": "woman",
    "men": "man",
    "people": "person",
    "persons": "person",
    "took": "take",
    "taken": "take",
    "taking": "take",
    "seized": "seize",
    "seizing": "seize",
    "beaten": "beat",
    "shot": "shoot",
    "married": "marry",
    "lying": "lie",
    "dies": "die",
    "died": "die",
    "dying": "die",
    "criticize": "criticise",
    "criticizing": "criticise",
    "naturalization": "naturalisation",
    "naturalize": "naturalise",
    "defense": "defence",
    "labor": "labour",
    "nigerian": "nigeria",
    "nigerians": "nigeria",
    "presidency": "president",
    "presidential": "president",
    "governorship": "governor",
    "qualification": "qualify",
    "qualifications": "qualify",
    "qualified": "qualify",
    "qualifies": "qualify",
    "disqualification": "disqualify",
    "disqualifications": "disqualify",
    "disqualified": "disqualify",
    "disqualifies": "disqualify",
}


def _stem(word: str) -> str:
    word = _LEMMAS.get(word, word)
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith(("sses", "xes", "zes", "ches", "shes")):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ied", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)] + ("y" if suffix == "ied" else "")
            if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeioulsz":
                word = word[:-1]
            break
    # Drop a final "e" so "leave", "leaving" and "leaves" agree.
    if len(word) > 3 and word.endswith("e") and not word.endswith("ee"):
        word = word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """Normalise text to comparable content tokens."""
    return [
        _stem(word)
        for word in _TOKEN.findall(text.lower().replace("’", "'").replace("'", ""))
        if word not in STOPWORDS
    ]


def _same(phrase_token: str, query_token: str) -> bool:
    if phrase_token == query_token:
        return True
    shorter, longer = sorted((phrase_token, query_token), key=len)
    return len(shorter) >= 6 and longer.startswith(shorter)


def _span(phrase_tokens: list[str], query_tokens: list[str]) -> int | None:
    """Smallest window of the query containing every phrase token, in any order."""
    positions = [
        [index for index, token in enumerate(query_tokens) if _same(word, token)]
        for word in phrase_tokens
    ]
    if any(not found for found in positions):
        return None
    if len(positions) == 1:
        return 1
    return min(
        max(combo) - min(combo) + 1
        for combo in itertools.islice(itertools.product(*positions), 256)
    )


@dataclass(frozen=True)
class Topic:
    slug: str
    # Section numbers, or path suffixes such as "oath-president" for
    # schedule items.
    sections: tuple[str, ...]
    phrases: tuple[str, ...]
    # Umbrella topics yield to a more specific topic in the same question.
    broad: bool = False


@dataclass(frozen=True)
class TopicMatch:
    slug: str
    sections: tuple[str, ...]
    score: float
    phrase: str


# Ordered roughly by how often people ask. Phrases are matched as bags of
# content tokens, so "search phone" matches "can police search my phone".
TOPICS: tuple[Topic, ...] = (
    Topic(
        "privacy",
        ("37",),
        (
            "privacy",
            "private life",
            "family life",
            "phone",
            "telephone",
            "phone call",
            "tap phone",
            "wiretap",
            "intercept",
            "surveillance",
            "spy",
            "read messages",
            "chat",
            "whatsapp",
            "text message",
            "email",
            "correspondence",
            "letter",
            "search phone",
            "check phone",
            "search house",
            "search home",
            "enter home",
            "enter house",
            "raid house",
            "personal data",
            "personal information",
        ),
    ),
    Topic(
        "arrest-detention",
        ("35",),
        (
            "arrest",
            "detain",
            "detention",
            "custody",
            "police station",
            "lock up",
            "locked up",
            "police cell",
            "bail",
            "remain silent",
            "right to silence",
            "keep quiet",
            "reason arrest",
            "grounds arrest",
            "24 hours",
            "48 hours",
            "brought before court",
            "charge court",
            "without charge",
            "personal liberty",
            "liberty",
            "held without",
            "police carry",
            "unlawful arrest",
            "wrongful arrest",
            "unlawful detention",
            "compensation apology",
        ),
    ),
    Topic(
        "legal-representation",
        ("35", "36"),
        ("lawyer", "legal practitioner", "legal representation", "counsel"),
    ),
    Topic(
        "fair-hearing",
        ("36",),
        (
            "fair hearing",
            "fair trial",
            "trial",
            "presumed innocent",
            "presumption innocence",
            "innocent until proven guilty",
            "proven guilty",
            "interpreter",
            "double jeopardy",
            "tried twice",
            "retroactive",
            "retrospective",
            "secret trial",
            "public trial",
            "self incrimination",
            "testify against myself",
            "evidence against myself",
            "right to be heard",
            "hear my side",
            "accused person",
            "charged offence",
            "criminal charge",
        ),
    ),
    Topic(
        "dignity-torture",
        ("34",),
        (
            "torture",
            "dignity",
            "inhuman",
            "degrading",
            "beat",
            "slap",
            "flog",
            "slavery",
            "slave",
            "servitude",
            "forced labour",
            "forced work",
            "police brutality",
            "brutality",
            "maltreat",
            "trafficking",
        ),
    ),
    Topic(
        "right-to-life",
        ("33",),
        (
            "right to life",
            "kill",
            "death penalty",
            "capital punishment",
            "execution",
            "executed",
            "extrajudicial",
            "shoot",
            "self defence",
            "deadly force",
            "lethal force",
            "riot",
            "kill arrest",
            "police kill",
            "police shoot",
        ),
    ),
    Topic(
        "expression-press",
        ("39",),
        (
            "freedom of speech",
            "free speech",
            "speech",
            "expression",
            "opinion",
            "criticise",
            "press",
            "journalist",
            "newspaper",
            "television",
            "tv station",
            "radio",
            "media",
            "social media",
            "tweet",
            "post online",
            "blog",
            "publish",
            "broadcast",
            "censor",
            "censorship",
            "access information",
            "receive information",
            "impart information",
        ),
    ),
    Topic(
        "religion-conscience",
        ("38",),
        (
            "religion",
            "religious",
            "change religion",
            "convert",
            "worship",
            "church",
            "mosque",
            "hijab",
            "faith",
            "belief",
            "religious instruction",
            "secret society",
            "cult",
            "cultism",
            "conscience",
            "freedom of thought",
            "atheist",
            "pray",
            "prayer",
        ),
    ),
    Topic(
        "assembly-association",
        ("40",),
        (
            "protest",
            "demonstration",
            "demonstrate",
            "rally",
            "march",
            "peaceful assembly",
            "assemble",
            "gathering",
            "association",
            "associate",
            "trade union",
            "union",
            "join political party",
            "join party",
            "peaceful group",
            "permission meet",
            "group meet",
            "public meeting",
            "hold meeting",
            "police permit",
        ),
    ),
    Topic(
        "movement",
        ("41",),
        (
            "freedom of movement",
            "move freely",
            "travel",
            "live anywhere",
            "reside",
            "residence",
            "live any state",
            "live another state",
            "deport",
            "expel",
            "expelled",
            "leave nigeria",
            "enter nigeria",
            "exit nigeria",
            "travel ban",
            "travel abroad",
            "extradition",
            "extradite",
        ),
    ),
    Topic(
        "discrimination",
        ("42",),
        (
            "discrimination",
            "discriminate",
            "tribe",
            "tribal",
            "ethnic",
            "ethnicity",
            "state of origin",
            "place of origin",
            "indigene",
            "sex",
            "gender",
            "woman",
            "female",
            "political opinion",
            "circumstances of birth",
            "out of wedlock",
            "illegitimate",
            "equal treatment",
            "equal rights",
        ),
    ),
    Topic(
        "own-property",
        ("43",),
        (
            "own property",
            "own land",
            "buy land",
            "buy property",
            "acquire property",
            "own house",
            "land another state",
            "property anywhere",
            "immovable property",
        ),
    ),
    Topic(
        "compulsory-acquisition",
        ("44",),
        (
            "compulsory acquisition",
            "compulsorily acquired",
            "take land",
            "take property",
            "seize property",
            "seize",
            "seizure",
            "confiscate",
            "demolish",
            "demolition",
            "compensation land",
            "compensation property",
            "acquire land",
            "minerals",
            "mineral",
            "who owns oil",
            "oil belong",
            "petroleum",
        ),
    ),
    Topic("land", ("43", "44"), ("land",), broad=True),
    Topic(
        "restricting-rights",
        ("45",),
        (
            "restrict rights",
            "limit rights",
            "rights limited",
            "rights restricted",
            "derogation",
            "suspend rights",
            "rights absolute",
            "absolute right",
            "national security",
            "public safety",
            "public morality",
            "public health",
        ),
    ),
    Topic(
        "enforcing-rights",
        ("46",),
        (
            "rights violated",
            "violation rights",
            "violate rights",
            "breach rights",
            "enforce rights",
            "enforcement rights",
            "fundamental rights enforcement",
            "sue police",
            "fundamental rights claim",
            "rights claim",
            "fundamental rights case",
            "fundamental rights action",
            "legal aid",
            "redress",
            "remedy",
        ),
    ),
    Topic(
        "supremacy",
        ("1",),
        (
            "supremacy",
            "supreme law",
            "highest law",
            "override",
            "overridden",
            "inconsistent law",
            "inconsistent",
            "void",
        ),
    ),
    Topic(
        "unity",
        ("2",),
        (
            "indivisible",
            "indissoluble",
            "secede",
            "secession",
            "break up",
            "divide nigeria",
        ),
    ),
    Topic(
        "states-list",
        ("3",),
        (
            "how many states",
            "number of states",
            "36 states",
            "list of states",
            "states of the federation",
            "names of states",
            "local government areas",
        ),
    ),
    Topic(
        "legislative-powers",
        ("4",),
        (
            "legislative power",
            "make laws",
            "making laws",
            "power make law",
            "exclusive legislative list",
            "concurrent legislative list",
            "exclusive list",
            "concurrent list",
            "residual",
        ),
    ),
    Topic("executive-powers", ("5",), ("executive power",)),
    Topic(
        "judicial-powers",
        ("6",),
        ("judicial power", "superior courts", "justiciable", "non justiciable"),
    ),
    Topic(
        "local-government",
        ("7",),
        (
            "local government",
            "lga",
            "council chairman",
            "local council",
            "local government autonomy",
            "local government election",
        ),
    ),
    Topic(
        "new-states",
        ("8",),
        (
            "create new state",
            "creation of state",
            "state creation",
            "new state",
            "boundary adjustment",
        ),
    ),
    Topic(
        "amendment",
        ("9",),
        (
            "amend",
            "amendment",
            "alter constitution",
            "alteration",
            "change constitution",
            "constitutional review",
            "rewrite",
        ),
    ),
    Topic(
        "state-religion",
        ("10",),
        (
            "state religion",
            "secular",
            "official religion",
            "government religion",
            "national religion",
        ),
    ),
    Topic(
        "public-order",
        ("11",),
        ("public order", "public security"),
    ),
    Topic(
        "treaties",
        ("12",),
        (
            "treaty",
            "international agreement",
            "domesticate",
            "international law",
            "convention force law",
        ),
    ),
    Topic(
        "state-policy",
        ("13", "14"),
        (
            "fundamental objectives",
            "directive principles",
            "chapter two",
            "chapter 2",
            "chapter ii",
            "federal character",
            "sovereignty belong",
            "welfare of the people",
            "security and welfare",
            "purpose of government",
        ),
    ),
    Topic(
        "political-objectives",
        ("15",),
        ("motto", "national integration", "unity and faith"),
    ),
    Topic(
        "economic-objectives",
        ("16",),
        (
            "economic objectives",
            "economy",
            "minimum wage",
            "living wage",
            "shelter",
            "food",
            "unemployment",
        ),
    ),
    Topic(
        "social-objectives",
        ("17",),
        (
            "social objectives",
            "equal pay",
            "health care",
            "healthcare",
            "medical",
            "hospital",
            "child exploitation",
            "child labour",
            "old age",
        ),
    ),
    Topic(
        "education",
        ("18",),
        (
            "education",
            "free education",
            "school fees",
            "illiteracy",
            "free primary education",
            "university",
        ),
    ),
    Topic("foreign-policy", ("19",), ("foreign policy", "international relations")),
    Topic(
        "environment",
        ("20",),
        ("environment", "environmental", "pollution", "wildlife", "forest", "climate"),
    ),
    Topic("culture", ("21",), ("culture", "cultural", "tradition")),
    Topic(
        "mass-media",
        ("22",),
        ("mass media", "media obligation", "hold government accountable"),
    ),
    Topic(
        "national-ethics",
        ("23",),
        ("national ethics", "integrity", "dignity of labour"),
    ),
    Topic(
        "citizen-duties",
        ("24",),
        (
            "duties of citizen",
            "duty of citizen",
            "citizen duty",
            "civic duty",
            "obligation of citizen",
            "pay tax",
            "respect flag",
            "national anthem",
        ),
    ),
    Topic(
        "citizenship",
        ("25", "26", "27"),
        (
            "citizenship",
            "nigerian citizen",
            "become nigerian",
            "become citizen",
            "qualify citizen",
        ),
        broad=True,
    ),
    Topic(
        "citizenship-birth",
        ("25",),
        (
            "citizen by birth",
            "born in nigeria",
            "nigerian by birth",
            "parents nigerian",
            "grandparent",
        ),
    ),
    Topic(
        "citizenship-registration",
        ("26",),
        (
            "marry nigerian",
            "married nigerian",
            "marriage citizenship",
            "wife citizenship",
            "husband citizenship",
            "foreign wife",
            "foreign husband",
            "citizenship by registration",
        ),
    ),
    Topic(
        "citizenship-naturalisation",
        ("27",),
        (
            "naturalisation",
            "naturalise",
            "foreigner become nigerian",
            "foreigner citizen",
            "foreigner citizenship",
        ),
    ),
    Topic(
        "dual-citizenship",
        ("28",),
        (
            "dual citizenship",
            "dual nationality",
            "two passports",
            "second passport",
            "another citizenship",
            "citizenship another country",
            "foreign citizenship",
            "two citizenship",
        ),
    ),
    Topic(
        "renounce-citizenship",
        ("29",),
        (
            "renounce",
            "renounce citizenship",
            "renunciation",
            "give up citizenship",
            "stop being a nigerian citizen",
        ),
    ),
    Topic(
        "lose-citizenship",
        ("30",),
        (
            "deprived of citizenship",
            "deprivation citizenship",
            "lose citizenship",
            "strip citizenship",
            "take away citizenship",
            "revoke citizenship",
        ),
    ),
    Topic(
        "national-assembly",
        ("47", "48", "49"),
        (
            "national assembly",
            "senate",
            "senator",
            "house of representatives",
            "reps",
            "how many senators",
            "number of senators",
            "lawmakers",
            "legislature",
        ),
        broad=True,
    ),
    Topic("presiding-officers", ("50",), ("senate president", "speaker")),
    Topic("quorum", ("54", "96"), ("quorum",)),
    Topic(
        "languages",
        ("55", "97"),
        (
            "official language",
            "hausa",
            "igbo",
            "ibo",
            "yoruba",
            "language national assembly",
            "language house of assembly",
        ),
    ),
    Topic(
        "bills",
        ("58", "59"),
        (
            "bill become law",
            "pass bill",
            "passing bill",
            "assent",
            "veto",
            "override veto",
            "money bill",
            "how laws are made",
            "how law made",
        ),
    ),
    Topic(
        "assembly-qualification",
        ("65", "66"),
        (
            "qualify senate",
            "qualification senator",
            "become senator",
            "run for senate",
            "contest senate",
            "senator age",
            "how old senator",
            "become member house of representatives",
            "run for house of representatives",
            "contest house of representatives",
        ),
    ),
    Topic(
        "defection",
        ("68", "109"),
        (
            "defect",
            "defection",
            "cross carpet",
            "decamp",
            "change party",
            "lose seat",
            "vacate seat",
            "seat vacant",
        ),
    ),
    Topic(
        "recall",
        ("69",),
        (
            "recall",
            "recall senator",
            "recall rep",
            "recall member",
            "recall national assembly",
            "remove senator",
            "remove rep",
        ),
    ),
    Topic(
        "recall-state",
        ("110",),
        ("recall house of assembly", "recall state assembly", "recall state lawmaker"),
    ),
    Topic(
        "legislator-pay",
        ("70",),
        (
            "senator salary",
            "lawmaker salary",
            "salary of senator",
            "senator allowance",
            "legislator salary",
        ),
    ),
    Topic(
        "voting",
        ("77", "117"),
        (
            "right to vote",
            "vote",
            "voting",
            "voting age",
            "who can vote",
            "register to vote",
            "eligible to vote",
            "voter",
            "franchise",
        ),
    ),
    Topic(
        "inec",
        ("78", "153"),
        (
            "inec",
            "electoral commission",
            "conduct election",
            "supervise election",
            "election umpire",
        ),
    ),
    Topic(
        "budget",
        ("80", "81", "82"),
        (
            "budget",
            "appropriation",
            "public funds",
            "public money",
            "consolidated revenue fund",
            "spend money",
        ),
    ),
    Topic("audit", ("85", "86"), ("auditor general", "audit", "public accounts")),
    Topic(
        "legislative-investigations",
        ("88", "89"),
        (
            "national assembly investigate",
            "probe",
            "investigative hearing",
            "summon",
            "summons",
            "oversight",
            "expose corruption",
        ),
    ),
    Topic(
        "state-assembly",
        ("90", "91"),
        ("house of assembly", "state assembly", "state lawmaker"),
    ),
    Topic(
        "state-assembly-qualification",
        ("106", "107"),
        (
            "run for house of assembly",
            "qualify house of assembly",
            "contest house of assembly",
        ),
    ),
    Topic(
        "oath",
        ("oath-president", "oath-governor", "140", "185"),
        ("oath of office", "swearing in", "sworn in", "oath", "swear"),
        broad=True,
    ),
    Topic(
        "oath-president",
        ("oath-president", "140"),
        ("president oath", "president swear"),
    ),
    Topic(
        "oath-governor", ("oath-governor", "185"), ("governor oath", "governor swear")
    ),
    Topic(
        "oath-allegiance", ("oath-allegiance",), ("oath of allegiance", "allegiance")
    ),
    Topic(
        "oath-legislator",
        ("oath-legislator", "52", "94"),
        (
            "oath national assembly",
            "oath house of assembly",
            "oath lawmaker",
            "oath legislator",
            "oath member",
            "member oath",
        ),
    ),
    Topic(
        "oath-judicial",
        ("oath-judicial", "290"),
        ("judicial oath", "judge oath", "oath judge"),
    ),
    Topic(
        "president-office",
        ("130", "5"),
        (
            "president power",
            "powers of president",
            "commander in chief",
            "head of state",
        ),
    ),
    Topic(
        "president-qualification",
        ("131", "137"),
        (
            "qualify president",
            "qualification president",
            "president qualification",
            "presidential qualification",
            "become president",
            "run for president",
            "contest president",
            "age president",
            "how old president",
            "president age",
            "requirements president",
            "eligible president",
            "presidential candidate",
        ),
    ),
    Topic(
        "presidential-election",
        ("132", "133", "134"),
        (
            "presidential election",
            "elect president",
            "win presidential election",
            "president elected",
            "25 percent",
            "two thirds of states",
            "run off",
            "runoff",
            "second ballot",
        ),
    ),
    Topic(
        "president-term",
        ("135", "137"),
        (
            "president term",
            "presidential term",
            "how long president",
            "tenure president",
            "third term",
            "two terms",
            "term limit",
            "four years term",
        ),
    ),
    Topic(
        "president-disqualification",
        ("137",),
        ("disqualify president", "forged certificate"),
    ),
    Topic("vice-president", ("141", "142"), ("vice president", "running mate")),
    Topic(
        "impeach-president",
        ("143",),
        (
            "impeach",
            "impeachment",
            "remove president",
            "removal of president",
            "gross misconduct",
        ),
    ),
    Topic(
        "president-incapacity",
        ("144",),
        (
            "president incapacity",
            "president sick",
            "president ill",
            "permanent incapacity",
            "medical incapacity",
        ),
    ),
    Topic(
        "acting-president",
        ("145",),
        (
            "acting president",
            "president travel",
            "president vacation",
            "president absent",
            "transmit letter",
        ),
    ),
    Topic(
        "president-succession",
        ("146",),
        (
            "president die",
            "death of president",
            "succeed president",
            "succession",
            "president resign",
        ),
    ),
    Topic(
        "ministers",
        ("147", "148"),
        (
            "minister",
            "appoint minister",
            "cabinet",
            "federal executive council",
            "minister every state",
        ),
    ),
    Topic(
        "attorney-general",
        ("150", "195"),
        ("attorney general", "minister of justice", "attorney general federation"),
    ),
    Topic(
        "federal-bodies",
        ("153",),
        (
            "federal commission",
            "code of conduct bureau",
            "police service commission",
            "federal character commission",
            "national judicial council",
            "njc",
            "federal civil service commission",
        ),
    ),
    Topic(
        "revenue-allocation",
        ("162",),
        (
            "federation account",
            "revenue allocation",
            "revenue sharing",
            "sharing formula",
            "derivation",
            "13 percent",
            "faac",
            "oil revenue",
            "distributable pool",
            "state allocation",
        ),
    ),
    Topic(
        "presidential-appointments",
        ("171",),
        (
            "presidential appointment",
            "ambassador",
            "head of service",
            "permanent secretary",
        ),
    ),
    Topic(
        "code-of-conduct",
        ("172", "209"),
        (
            "code of conduct",
            "asset declaration",
            "declare asset",
            "declaration of asset",
        ),
    ),
    Topic(
        "prosecutions",
        ("174", "211"),
        (
            "public prosecution",
            "nolle prosequi",
            "discontinue case",
            "take over prosecution",
            "prosecute",
            "prosecution",
        ),
    ),
    Topic(
        "pardon",
        ("175", "212"),
        ("pardon", "prerogative of mercy", "clemency", "commute sentence", "reprieve"),
    ),
    Topic(
        "governor-office",
        ("176",),
        ("governor power", "powers of governor"),
    ),
    Topic(
        "governor-qualification",
        ("177", "182"),
        (
            "qualify governor",
            "qualification governor",
            "governor qualification",
            "become governor",
            "run for governor",
            "contest governor",
            "governor age",
            "how old governor",
            "requirements governor",
            "governorship candidate",
        ),
    ),
    Topic(
        "governorship-election",
        ("178", "179"),
        ("governorship election", "elect governor", "win governorship"),
    ),
    Topic(
        "governor-term",
        ("180", "182"),
        ("governor term", "governor tenure", "how long governor"),
    ),
    Topic("deputy-governor", ("186", "187"), ("deputy governor",)),
    Topic(
        "impeach-governor",
        ("188",),
        (
            "impeach governor",
            "remove governor",
            "removal of governor",
            "governor impeachment",
            "remove deputy governor",
        ),
    ),
    Topic("acting-governor", ("190",), ("acting governor",)),
    Topic(
        "commissioners",
        ("192",),
        (
            "state commissioner",
            "commissioner",
            "appoint commissioner",
            "state executive council",
        ),
    ),
    Topic("census", ("213",), ("census", "population count", "headcount")),
    Topic(
        "police",
        ("214", "215"),
        (
            "state police",
            "police force",
            "own police",
            "community police",
            "regional police",
            "local police",
            "amotekun",
            "establish police",
            "nigeria police",
        ),
    ),
    Topic(
        "police-control",
        ("215", "216"),
        (
            "inspector general",
            "igp",
            "commissioner of police",
            "control police",
            "controls police",
            "command police",
            "police council",
        ),
    ),
    Topic(
        "armed-forces",
        ("217", "218"),
        (
            "armed forces",
            "army",
            "military",
            "navy",
            "air force",
            "soldier",
            "deploy army",
            "military deployment",
        ),
    ),
    Topic(
        "military-service",
        ("220",),
        ("compulsory military service", "conscription", "national service"),
    ),
    Topic(
        "independent-candidates",
        ("221",),
        (
            "independent candidate",
            "independent candidacy",
            "run without party",
            "contest without party",
        ),
    ),
    Topic(
        "party-registration",
        ("222", "223"),
        (
            "form political party",
            "register political party",
            "political party registration",
            "new party",
            "form party",
        ),
    ),
    Topic(
        "party-finance",
        ("225", "226"),
        ("party finance", "party funding", "campaign finance", "fund political party"),
    ),
    Topic(
        "militia", ("227",), ("militia", "quasi military", "armed group", "vigilante")
    ),
    Topic("supreme-court", ("230", "231"), ("supreme court",)),
    Topic(
        "judicial-appointments",
        ("231",),
        (
            "chief justice",
            "cjn",
            "justice supreme court",
            "appoint judge",
            "appointment of judge",
        ),
    ),
    Topic(
        "supreme-court-original",
        ("232",),
        (
            "dispute between federation and state",
            "state sue federal government",
            "original jurisdiction",
        ),
    ),
    Topic(
        "supreme-court-appeal",
        ("233",),
        ("appeal to supreme court", "appeal supreme court"),
    ),
    Topic(
        "court-of-appeal", ("237", "240", "241"), ("court of appeal", "appeal court")
    ),
    Topic(
        "federal-high-court-jurisdiction",
        ("251",),
        ("federal high court jurisdiction", "jurisdiction federal high court"),
    ),
    Topic(
        "federal-high-court",
        ("249", "251"),
        ("federal high court", "fhc", "admiralty", "tax case", "revenue case"),
    ),
    Topic(
        "state-high-court",
        ("270", "272"),
        ("state high court", "high court of a state", "high court jurisdiction"),
    ),
    Topic(
        "sharia-court",
        ("275", "277"),
        ("sharia", "sharia court", "islamic law", "kadi"),
    ),
    Topic("customary-court", ("280", "282"), ("customary court", "customary law")),
    Topic(
        "election-petitions",
        ("285",),
        (
            "election tribunal",
            "election petition",
            "challenge election",
            "election result",
            "tribunal election",
            "petition election",
        ),
    ),
    Topic(
        "court-orders",
        ("287",),
        (
            "enforce judgment",
            "obey court order",
            "disobey court order",
            "court order enforcement",
            "contempt",
        ),
    ),
    Topic(
        "judges-tenure",
        ("291", "292"),
        (
            "judge retire",
            "retirement age judge",
            "remove judge",
            "removal of judge",
            "sack judge",
            "judicial misconduct",
        ),
    ),
    Topic(
        "fct",
        ("297", "299", "302"),
        ("fct", "federal capital territory", "abuja", "fct minister", "abuja land"),
    ),
    Topic(
        "state-of-emergency",
        ("305",),
        (
            "state of emergency",
            "emergency rule",
            "declare emergency",
            "proclamation of emergency",
            "emergency power",
        ),
    ),
    Topic("resignation", ("306",), ("resign", "resignation")),
    Topic(
        "immunity",
        ("308",),
        (
            "immunity",
            "immune",
            "sue governor",
            "sue president",
            "sue vice president",
            "sue deputy governor",
            "arrest governor",
            "arrest president",
            "prosecute governor",
            "prosecute president",
            "governor court case",
            "president court case",
        ),
    ),
    Topic(
        "existing-law",
        ("315",),
        ("existing law", "military decree", "decree", "law before 1999"),
    ),
    Topic("interpretation", ("318",), ("interpretation", "definition", "define")),
    Topic(
        "civil-service",
        ("169", "206"),
        ("civil service", "civil servant", "public servant"),
    ),
    Topic("pension", ("173", "210"), ("pension", "gratuity")),
)

# Provisions that change how the main answer applies, added as context when a
# section is explained: restrictions on rights, and the paired
# disqualification rules for each office.
COMPANIONS: dict[str, tuple[str, ...]] = {
    "37": ("45",),
    "38": ("45",),
    "39": ("45",),
    "40": ("45",),
    "41": ("45",),
    "131": ("137",),
    "177": ("182",),
    "65": ("66",),
    "106": ("107",),
}

# Context for titles the source repeats across chapters, such as "Quorum".
_TITLE_CONTEXT: tuple[tuple[int, int, str], ...] = (
    (47, 89, "National Assembly"),
    (90, 129, "House of Assembly"),
    (130, 152, "President"),
    (153, 161, "federal bodies"),
    (176, 196, "Governor"),
    (197, 205, "state bodies"),
    (221, 229, "political parties"),
    (230, 236, "Supreme Court"),
    (237, 248, "Court of Appeal"),
    (249, 254, "Federal High Court"),
    (255, 259, "High Court of the FCT"),
    (260, 264, "Sharia Court of Appeal of the FCT"),
    (265, 269, "Customary Court of Appeal of the FCT"),
    (270, 274, "State High Court"),
    (275, 279, "State Sharia Court of Appeal"),
    (280, 284, "State Customary Court of Appeal"),
)
_GENERIC_TITLES = frozenset(
    title.casefold()
    for title in (
        "Quorum",
        "Languages",
        "Voting",
        "Committees",
        "Sittings",
        "Qualifications for election",
        "Disqualifications",
        "Recall",
        "Remuneration",
        "Tenure of seat of members",
        "Regulation of procedure",
        "Unqualified person sitting or voting",
        "Presiding at sittings",
        "Original jurisdiction",
        "Appellate jurisdiction",
        "Jurisdiction",
        "Constitution",
        "Practice and procedure",
        "Powers",
        "Interpretation",
        "Appointment of Chairman and members",
        "Tenure of office of members",
        "Tenure of office of the members",
        "Qualification for membership",
        "Removal of members",
        "Independence of certain bodies",
        "Quorum and decisions",
        "Powers and procedure",
        "Special Advisers",
        "Establishment of Consolidated Revenue Fund",
        "Contingencies Fund",
        "Audit of public accounts",
        "Appointment of Auditor-General",
        "Tenure of office of Auditor-General",
        "Power to conduct investigations",
        "Power as to matters of evidence",
        "Supervision of election",
        "Direct election and franchise",
    )
)


@cache
def _titles() -> dict[str, dict[str, str]]:
    data = json.loads(_TITLES_PATH.read_text(encoding="utf-8"))
    return {"sections": data["sections"], "chapters": data["chapters"]}


def section_number(canonical_path: str) -> str | None:
    match = _SECTION_IN_PATH.search(canonical_path)
    return match.group(1) if match else None


def section_title(canonical_path: str) -> str | None:
    """Plain title for a section, or for the section containing a sub-provision."""
    number = section_number(canonical_path)
    if number is None:
        chapter = _CHAPTER_IN_PATH.search(canonical_path)
        if chapter and canonical_path.endswith(f".chapter{chapter.group(1)}"):
            return _titles()["chapters"].get(chapter.group(1))
        return None
    title = _titles()["sections"].get(number)
    if title is None:
        return None
    if title.casefold() in _GENERIC_TITLES and number.isdigit():
        value = int(number)
        for start, end, context in _TITLE_CONTEXT:
            if start <= value <= end:
                return f"{title} ({context})"
    return title


def match_topics(query: str, *, limit: int = 3) -> list[TopicMatch]:
    """Rank topics by how much of the question their matched phrases explain.

    A phrase matches when all its words appear close together, in any order.
    """
    query_tokens = tokens(query)
    if not query_tokens:
        return []
    matches: list[TopicMatch] = []
    for topic in TOPICS:
        covered: set[int] = set()
        best = ""
        for phrase in topic.phrases:
            phrase_tokens = list(dict.fromkeys(tokens(phrase)))
            if not phrase_tokens:
                continue
            span = _span(phrase_tokens, query_tokens)
            # Allow one unrelated word inside a phrase ("search my house").
            if span is None or span > len(phrase_tokens) + 1:
                continue
            covered.update(
                index
                for index, token in enumerate(query_tokens)
                if any(_same(word, token) for word in phrase_tokens)
            )
            if len(phrase_tokens) >= len(tokens(best) or [""]):
                best = phrase
        if covered:
            score = len(covered) - (0.5 if topic.broad else 0.0)
            matches.append(
                TopicMatch(
                    slug=topic.slug,
                    sections=topic.sections,
                    score=score,
                    phrase=best,
                )
            )
    # Stable sort keeps the curated order for ties.
    matches.sort(key=lambda item: -item.score)
    return matches[:limit]


def topic_sections(query: str) -> list[tuple[str, float]]:
    """Ordered section numbers for a query with a fusion weight for each.

    Multi-word matches are specific enough to lead the ranking; single-word
    matches only nudge it, so dense and keyword search can still win.
    """
    ordered: list[tuple[str, float]] = []
    seen: set[str] = set()
    for match in match_topics(query):
        weight = 2.5 if match.score >= 2 else 1.5
        for number in match.sections:
            if number not in seen:
                seen.add(number)
                ordered.append((number, weight))
    if _REMEDY_INTENT.search(query) and "46" not in seen:
        ordered.append(("46", 1.5))
    return ordered


def companion_sections(number: str) -> tuple[str, ...]:
    return COMPANIONS.get(number, ())
