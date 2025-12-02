# ============================
# Province Name Constants
# ============================

ACEH = "Aceh"
BALI = "Bali"
BANGKA_BELITUNG = "Bangka Belitung"
BANTEN = "Banten"
BENGKULU = "Bengkulu"
DI_YOGYAKARTA = "DI Yogyakarta"
DKI_JAKARTA = "DKI Jakarta"
GORONTALO = "Gorontalo"
JAMBI = "Jambi"
JAWA_BARAT = "Jawa Barat"
JAWA_TENGAH = "Jawa Tengah"
JAWA_TIMUR = "Jawa Timur"
KALBAR = "Kalimantan Barat"
KALSEL = "Kalimantan Selatan"
KALTENG = "Kalimantan Tengah"
KALTIM = "Kalimantan Timur"
KALTARA = "Kalimantan Utara"
KEPRI = "Kepulauan Riau"
LAMPUNG = "Lampung"
MALUKU = "Maluku"
MALUKU_UTARA = "Maluku Utara"
NTB = "Nusa Tenggara Barat"
NTT = "Nusa Tenggara Timur"
PAPUA = "Papua"
PAPUA_BARAT = "Papua Barat"
PAPUA_BARAT_DAYA = "Papua Barat Daya"
PAPUA_PEGUNUNGAN = "Papua Pegunungan"
PAPUA_SELATAN = "Papua Selatan"
PAPUA_TENGAH = "Papua Tengah"
RIAU = "Riau"
SULBAR = "Sulawesi Barat"
SULSEL = "Sulawesi Selatan"
SULTENG = "Sulawesi Tengah"
SULTRA = "Sulawesi Tenggara"
SULUT = "Sulawesi Utara"
SUMBAR = "Sumatera Barat"
SUMSEL = "Sumatera Selatan"
SUMUT = "Sumatera Utara"


# ============================
# Province -> ISO 3166-2 Codes
# ============================

PROVINCE_TO_CODE = {
    ACEH: "ID-AC",
    BALI: "ID-BA",
    BANGKA_BELITUNG: "ID-BB",
    BANTEN: "ID-BT",
    BENGKULU: "ID-BE",
    DI_YOGYAKARTA: "ID-YO",
    DKI_JAKARTA: "ID-JK",
    GORONTALO: "ID-GO",
    JAMBI: "ID-JA",
    JAWA_BARAT: "ID-JB",
    JAWA_TENGAH: "ID-JT",
    JAWA_TIMUR: "ID-JI",
    KALBAR: "ID-KB",
    KALSEL: "ID-KS",
    KALTENG: "ID-KT",
    KALTIM: "ID-KI",
    KALTARA: "ID-KU",
    KEPRI: "ID-KR",
    LAMPUNG: "ID-LA",
    MALUKU: "ID-MA",
    MALUKU_UTARA: "ID-MU",
    NTB: "ID-NB",
    NTT: "ID-NT",
    PAPUA: "ID-PA",
    PAPUA_BARAT: "ID-PB",
    PAPUA_BARAT_DAYA: "ID-PD",
    PAPUA_PEGUNUNGAN: "ID-PP",
    PAPUA_SELATAN: "ID-PS",
    PAPUA_TENGAH: "ID-PT",
    RIAU: "ID-RI",
    SULBAR: "ID-SR",
    SULSEL: "ID-SN",
    SULTENG: "ID-ST",
    SULTRA: "ID-SG",
    SULUT: "ID-SA",
    SUMBAR: "ID-SB",
    SUMSEL: "ID-SS",
    SUMUT: "ID-SU"
}


# ============================
# Aliases (all referencing constants)
# ============================

PROVINCE_ALIASES = {
    "aceh": ACEH,
    "nanggroe aceh darussalam": ACEH,

    "bali": BALI,

    "bangka belitung": BANGKA_BELITUNG,
    "bangka-belitung": BANGKA_BELITUNG,
    "kepulauan bangka belitung": BANGKA_BELITUNG,
    "kep. bangka belitung": BANGKA_BELITUNG,
    "bangka belitung islands": BANGKA_BELITUNG,

    "banten": BANTEN,
    "bengkulu": BENGKULU,

    "di yogyakarta": DI_YOGYAKARTA,
    "daerah istimewa yogyakarta": DI_YOGYAKARTA,
    "d.i. yogyakarta": DI_YOGYAKARTA,
    "diy": DI_YOGYAKARTA,
    "special region of yogyakarta": DI_YOGYAKARTA,
    "special region of jogjakarta": DI_YOGYAKARTA,

    "dki jakarta": DKI_JAKARTA,
    "jakarta": DKI_JAKARTA,

    "gorontalo": GORONTALO,
    "jambi": JAMBI,

    "jawa barat": JAWA_BARAT,
    "west java": JAWA_BARAT,

    "jawa tengah": JAWA_TENGAH,
    "central java": JAWA_TENGAH,

    "jawa timur": JAWA_TIMUR,
    "east java": JAWA_TIMUR,

    "kalimantan barat": KALBAR,
    "west kalimantan": KALBAR,

    "kalimantan selatan": KALSEL,
    "south kalimantan": KALSEL,

    "kalimantan tengah": KALTENG,
    "central kalimantan": KALTENG,

    "kalimantan timur": KALTIM,
    "east kalimantan": KALTIM,

    "kalimantan utara": KALTARA,
    "north kalimantan": KALTARA,

    "kepulauan riau": KEPRI,
    "riau islands": KEPRI,

    "lampung": LAMPUNG,

    "maluku": MALUKU,
    "maluku utara": MALUKU_UTARA,
    "north maluku": MALUKU_UTARA,

    "nusa tenggara barat": NTB,
    "west nusa tenggara": NTB,

    "nusa tenggara timur": NTT,
    "east nusa tenggara": NTT,

    "papua": PAPUA,
    "papua barat": PAPUA_BARAT,
    "west papua": PAPUA_BARAT,

    "papua barat daya": PAPUA_BARAT_DAYA,

    "papua pegunungan": PAPUA_PEGUNUNGAN,
    "highland papua": PAPUA_PEGUNUNGAN,
    "highlands papua": PAPUA_PEGUNUNGAN,

    "papua selatan": PAPUA_SELATAN,
    "south papua": PAPUA_SELATAN,

    "papua tengah": PAPUA_TENGAH,
    "central papua": PAPUA_TENGAH,

    "riau": RIAU,

    "sulawesi barat": SULBAR,
    "west sulawesi": SULBAR,

    "sulawesi selatan": SULSEL,
    "south sulawesi": SULSEL,

    "sulawesi tengah": SULTENG,
    "central sulawesi": SULTENG,

    "sulawesi tenggara": SULTRA,
    "southeast sulawesi": SULTRA,

    "sulawesi utara": SULUT,
    "north sulawesi": SULUT,

    "sumatera barat": SUMBAR,
    "west sumatra": SUMBAR,

    "sumatera selatan": SUMSEL,
    "south sumatra": SUMSEL,

    "sumatera utara": SUMUT,
    "north sumatra": SUMUT,
}


# ============================
# Error message constants
# ============================

CLIMATE_ERROR_INVALID_FORMAT = "Invalid data format"
CLIMATE_ERROR_MISSING_PROVINCE = "Missing province field"
CLIMATE_ERROR_INVALID_VALUE = "Invalid value type"
