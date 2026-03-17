"""Comprehensive company to ticker mapping with fuzzy matching."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
from cachetools import LRUCache
from loguru import logger


@dataclass
class CompanyMapping:
    """Company mapping information."""
    name: str
    ticker: str
    aliases: List[str]
    parent_company: Optional[str] = None
    sector: str = "Biotechnology"
    market_cap_bucket: str = "mid"


class CompanyMapper:
    """Maps company names from ClinicalTrials.gov to stock tickers."""
    
    def __init__(self):
        self._mappings: Dict[str, CompanyMapping] = {}
        self._ticker_to_name: Dict[str, str] = {}
        self._alias_map: Dict[str, str] = {}  # alias -> canonical name
        self._cache = LRUCache(maxsize=1000)
        self._fuzzy_threshold = 0.85
        
        self._initialize_mappings()
    
    def _initialize_mappings(self):
        """Initialize comprehensive company mappings."""
        companies = [
            # Large Cap Pharma ($100B+)
            CompanyMapping("Pfizer", "PFE", ["pfizer inc", "pfizer incorporated", "pfizer pharmaceuticals"], market_cap_bucket="large"),
            CompanyMapping("Johnson & Johnson", "JNJ", ["johnson and johnson", "jnj", "janssen"], market_cap_bucket="large"),
            CompanyMapping("Roche", "RHHBY", ["roche holding", "f. hoffmann-la roche", "hoffmann-la roche", "genentech"], market_cap_bucket="large"),
            CompanyMapping("Novartis", "NVS", ["novartis ag", "novartis pharma"], market_cap_bucket="large"),
            CompanyMapping("Eli Lilly", "LLY", ["eli lilly and company", "lilly"], market_cap_bucket="large"),
            CompanyMapping("Merck", "MRK", ["merck & co", "merck and co", "msd", "merck sharp & dohme"], market_cap_bucket="large"),
            CompanyMapping("AbbVie", "ABBV", ["abbvie inc"], market_cap_bucket="large"),
            CompanyMapping("AstraZeneca", "AZN", ["astrazeneca plc", "astra zeneca"], market_cap_bucket="large"),
            CompanyMapping("Bristol Myers Squibb", "BMY", ["bristol-myers squibb", "bms"], market_cap_bucket="large"),
            CompanyMapping("Sanofi", "SNY", ["sanofi sa", "sanofi-aventis", "genzyme"], market_cap_bucket="large"),
            CompanyMapping("Novo Nordisk", "NVO", ["novo nordisk a/s"], market_cap_bucket="large"),
            CompanyMapping("Takeda", "TAK", ["takeda pharmaceutical"], market_cap_bucket="large"),
            CompanyMapping("Bayer", "BAYRY", ["bayer ag"], market_cap_bucket="large"),
            CompanyMapping("GSK", "GSK", ["glaxosmithkline", "glaxo smithkline", "glaxo"], market_cap_bucket="large"),
            CompanyMapping("Gilead Sciences", "GILD", ["gilead", "gilead sciences inc"], market_cap_bucket="large"),
            CompanyMapping("Amgen", "AMGN", ["amgen inc"], market_cap_bucket="large"),
            CompanyMapping("Vertex Pharmaceuticals", "VRTX", ["vertex", "vertex pharma"], market_cap_bucket="large"),
            
            # Mid Cap Pharma ($10B-$100B)
            CompanyMapping("Regeneron Pharmaceuticals", "REGN", ["regeneron", "regeneron pharma"], market_cap_bucket="large"),
            CompanyMapping("Biogen", "BIIB", ["biogen inc"], market_cap_bucket="large"),
            CompanyMapping("Moderna", "MRNA", ["moderna inc", "moderna tx", "moderna therapeutics"], market_cap_bucket="large"),
            CompanyMapping("Seagen", "PFE", ["seattle genetics", "seagen inc", "seagen"], market_cap_bucket="large", parent_company="Pfizer"),  # Acquired by Pfizer 2023
            CompanyMapping("BioNTech", "BNTX", ["biontech se", "biontech ag"], market_cap_bucket="large"),
            CompanyMapping("Horizon Therapeutics", "AMGN", ["horizon", "horizon therapeutics plc"], market_cap_bucket="mid", parent_company="Amgen"),  # Acquired by Amgen 2023
            CompanyMapping("Jazz Pharmaceuticals", "JAZZ", ["jazz pharma"], market_cap_bucket="mid"),
            CompanyMapping("Neurocrine Biosciences", "NBIX", ["neurocrine"], market_cap_bucket="mid"),
            CompanyMapping("Ionis Pharmaceuticals", "IONS", ["ionis", "ionis pharma", "isis pharmaceuticals"], market_cap_bucket="mid"),
            CompanyMapping("Alnylam Pharmaceuticals", "ALNY", ["alnylam", "alnylam pharma"], market_cap_bucket="mid"),
            CompanyMapping("Incyte", "INCY", ["incyte corporation", "incyte corp"], market_cap_bucket="mid"),
            CompanyMapping("Exact Sciences", "EXAS", ["exact sciences corporation"], market_cap_bucket="mid"),
            CompanyMapping("United Therapeutics", "UTHR", ["united therapeutics corporation"], market_cap_bucket="mid"),
            CompanyMapping("Blueprint Medicines", "RHHBY", ["blueprint medicines corporation", "blueprint medicines"], market_cap_bucket="mid", parent_company="Roche"),  # Acquired by Roche 2024
            CompanyMapping("Sarepta Therapeutics", "SRPT", ["sarepta", "sarepta therapeutics inc"], market_cap_bucket="mid"),
            CompanyMapping("argenx", "ARGX", ["argenx se", "argenx nv"], market_cap_bucket="large"),
            CompanyMapping("BeiGene", "BGNE", ["beigene ltd", "beigene limited"], market_cap_bucket="large"),
            CompanyMapping("Legend Biotech", "LEGN", ["legend biotech corporation"], market_cap_bucket="mid"),
            CompanyMapping("Ascendis Pharma", "ASND", ["ascendis pharma a/s"], market_cap_bucket="mid"),
            CompanyMapping("Apellis Pharmaceuticals", "APLS", ["apellis", "apellis pharmaceuticals inc"], market_cap_bucket="mid"),
            CompanyMapping("ACADIA Pharmaceuticals", "ACAD", ["acadia", "acadia pharmaceuticals inc"], market_cap_bucket="mid"),
            CompanyMapping("Exelixis", "EXEL", ["exelixis inc"], market_cap_bucket="mid"),
            CompanyMapping("Neumora Therapeutics", "NMRA", ["neumora"], market_cap_bucket="small"),
            CompanyMapping("Morphic Holding", "LLY", ["morphic", "morphic holding inc"], market_cap_bucket="small"),
            CompanyMapping("Daiichi Sankyo", "DSNKY", ["daiichi sankyo co", "daiichi sankyo company"], market_cap_bucket="large"),
            CompanyMapping("SpringWorks Therapeutics", "GPCR", ["springworks", "springworks therapeutics inc"], market_cap_bucket="mid"),
            CompanyMapping("Biohaven", "BHVN", ["biohaven therapeutics", "biohaven therapeutics ltd", "biohaven ltd", "biohaven pharmaceuticals"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Menarini Group", "MNRN.MI", ["menarini", "a. menarini", "berlin-chemie"], market_cap_bucket="mid"),  # delisted/acquired
            CompanyMapping("Jiangsu HengRui Medicine", "600276.SS", ["hengrui medicine", "jiangsu hengrui", "jiangsu hengrui medicine co"], market_cap_bucket="large"),
            CompanyMapping("Sun Pharma", "SUNPHARMA.NS", ["sun pharmaceutical", "sun pharma industries"], market_cap_bucket="large"),
            CompanyMapping("Zai Lab", "ZLAB", ["zai lab limited", "zai lab"], market_cap_bucket="small"),
            CompanyMapping("Hutchmed", "HCM", ["hutchmed limited", "hutchison medipharma"], market_cap_bucket="small"),
            CompanyMapping("BeiGene", "ONC", ["beigene oncology"], market_cap_bucket="large"),
            # REMOVED: CompanyMapping("EQRx", "EQRX", ["eqrx inc"], market_cap_bucket="small"),  # delisted/acquired
            
            # Small/Mid Cap Biotech ($1B-$10B)
            CompanyMapping("Arrowhead Pharmaceuticals", "ARWR", ["arrowhead", "arrowhead pharma"], market_cap_bucket="mid"),
            CompanyMapping("Intellia Therapeutics", "NTLA", ["intellia", "intellia therapeutics inc"], market_cap_bucket="mid"),
            CompanyMapping("Editas Medicine", "EDIT", ["editas", "editas medicine inc"], market_cap_bucket="small"),
            CompanyMapping("CRISPR Therapeutics", "CRSP", ["crispr therapeutics ag"], market_cap_bucket="mid"),
            CompanyMapping("Beam Therapeutics", "BEAM", ["beam", "beam therapeutics inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Verve Therapeutics", "VERV", ["verve", "verve therapeutics inc"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Reata Pharmaceuticals", "BIIB", ["reata", "reata pharmaceuticals inc"], market_cap_bucket="mid", parent_company="Biogen"),
            CompanyMapping("Karuna Therapeutics", "BMY", ["karuna", "karuna therapeutics inc"], market_cap_bucket="mid", parent_company="Bristol Myers Squibb"),  # Acquired by BMS 2024
            CompanyMapping("Cerevel Therapeutics", "ABBV", ["cerevel", "cerevel therapeutics"], market_cap_bucket="mid", parent_company="AbbVie"),  # Acquired by AbbVie 2024
            CompanyMapping("Mirati Therapeutics", "BMY", ["mirati", "mirati therapeutics inc"], market_cap_bucket="mid", parent_company="Bristol Myers Squibb"),  # Acquired by BMS 2024
            CompanyMapping("Karyopharm Therapeutics", "KPTI", ["karyopharm", "karyopharm therapeutics inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Deciphera Pharmaceuticals", "DCPH", ["deciphera", "deciphera pharmaceuticals inc"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Turning Point Therapeutics", "BMY", ["turning point", "turning point therapeutics"], market_cap_bucket="small", parent_company="Bristol Myers Squibb"),  # Acquired by BMS 2022
            CompanyMapping("Zymeworks", "ZYME", ["zymeworks inc"], market_cap_bucket="small"),
            CompanyMapping("Arcus Biosciences", "RCUS", ["arcus", "arcus biosciences inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("iTeos Therapeutics", "ITOS", ["iteos", "iteos therapeutics"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Tango Therapeutics", "TNGX", ["tango", "tango therapeutics"], market_cap_bucket="small"),
            CompanyMapping("Scholar Rock", "SRRK", ["scholar rock holding"], market_cap_bucket="small"),
            CompanyMapping("C4 Therapeutics", "CCCC", ["c4 therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Kymera Therapeutics", "KYMR", ["kymera", "kymera therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Foghorn Therapeutics", "FHTX", ["foghorn", "foghorn therapeutics"], market_cap_bucket="small"),
            CompanyMapping("Sana Biotechnology", "SANA", ["sana biotechnology inc"], market_cap_bucket="small"),
            CompanyMapping("Lyell Immunopharma", "LYEL", ["lyell immunopharma inc"], market_cap_bucket="small"),
            CompanyMapping("Nkarta", "NKTX", ["nkarta inc"], market_cap_bucket="small"),
            CompanyMapping("Caribou Biosciences", "CRBU", ["caribou biosciences inc"], market_cap_bucket="small"),
            CompanyMapping("Allogene Therapeutics", "ALLO", ["allogene therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Atara Biotherapeutics", "ATRA", ["atara biotherapeutics"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Adaptimmune Therapeutics", "ADAP", ["adaptimmune", "adaptimmune therapeutics plc"], market_cap_bucket="small"),  # delisted/acquired
            # REMOVED: CompanyMapping("TCR2 Therapeutics", "TCRR", ["tcr2 therapeutics inc"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Aurinia Pharmaceuticals", "AUPH", ["aurinia", "aurinia pharmaceuticals inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Calliditas Therapeutics", "CALT", ["calliditas", "calliditas therapeutics"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Travere Therapeutics", "TVTX", ["travere", "travere therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Amicus Therapeutics", "FOLD", ["amicus", "amicus therapeutics inc"], market_cap_bucket="mid"),
            CompanyMapping("BioMarin Pharmaceutical", "BMRN", ["biomarin", "biomarin pharmaceutical inc"], market_cap_bucket="large"),
            CompanyMapping("Ultragenyx Pharmaceutical", "RARE", ["ultragenyx", "ultragenyx pharmaceutical inc"], market_cap_bucket="mid"),
            CompanyMapping("Sarepta Therapeutics", "SRPT", ["sarepta", "sarepta therapeutics inc"], market_cap_bucket="mid"),
            CompanyMapping("PTC Therapeutics", "PTCT", ["ptc", "ptc therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Solid Biosciences", "SLDB", ["solid biosciences inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Myovant Sciences", "MYOV", ["myovant sciences", "myovant"], market_cap_bucket="small", parent_company="Sumitovant"),  # delisted/acquired
            CompanyMapping("Sumitovant Biopharma", "VTYX", ["sumitovant", "sumitovant biopharma"], market_cap_bucket="small"),
            CompanyMapping("Roivant Sciences", "ROIV", ["roivant sciences"], market_cap_bucket="mid"),
            CompanyMapping("Immunovant", "IMVT", ["immunovant inc", "immunovant sciences", "immunovant sciences gmbh"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Harpoon Therapeutics", "HARP", ["harpoon", "harpoon therapeutics"], market_cap_bucket="small", parent_company="Merck"),  # delisted/acquired
            CompanyMapping("Nurix Therapeutics", "NRIX", ["nurix", "nurix therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Cytokinetics", "CYTK", ["cytokinetics incorporated"], market_cap_bucket="mid"),
            CompanyMapping("Revolution Medicines", "RVMD", ["revolution medicines inc"], market_cap_bucket="mid"),
            CompanyMapping("Relay Therapeutics", "RLAY", ["relay therapeutics inc"], market_cap_bucket="small"),
            CompanyMapping("Erasca", "ERAS", ["erasca inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Flare Therapeutics", "FLRX", ["flare therapeutics"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Scorpion Therapeutics", "SCOR", ["scorpion therapeutics"], market_cap_bucket="small"),
            CompanyMapping("Rapport Therapeutics", "RAPP", ["rapport therapeutics"], market_cap_bucket="small"),
            CompanyMapping("Septerna", "SEPN", ["septerna inc"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Odyssey Therapeutics", "ODTX", ["odyssey therapeutics"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Insitro", "INRO", ["insitro"], market_cap_bucket="private"),
            CompanyMapping("Recursion Pharmaceuticals", "RXRX", ["recursion", "recursion pharmaceuticals"], market_cap_bucket="mid"),
            CompanyMapping("Exscientia", "RXRX", ["exscientia plc"], market_cap_bucket="small"),
            CompanyMapping("Schrödinger", "SDGR", ["schrodinger inc"], market_cap_bucket="small"),
            CompanyMapping("Relay Therapeutics", "RLAY", ["relay therapeutics"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("Berkeley Lights", "BLI", ["berkeley lights inc"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Ginkgo Bioworks", "DNA", ["ginkgo bioworks"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Zymergen", "ZY", ["zymergen inc"], market_cap_bucket="small", parent_company="Ginkgo"),  # delisted/acquired
            CompanyMapping("Twist Bioscience", "TWST", ["twist bioscience corporation"], market_cap_bucket="small"),
            CompanyMapping("Pacific Biosciences", "PACB", ["pacific biosciences of california"], market_cap_bucket="mid"),
            CompanyMapping("Oxford Nanopore", "ONT.L", ["oxford nanopore technologies"], market_cap_bucket="mid"),
            CompanyMapping("10x Genomics", "TXG", ["10x genomics inc"], market_cap_bucket="mid"),
            CompanyMapping("Guardant Health", "GH", ["guardant health inc"], market_cap_bucket="mid"),
            CompanyMapping("Natera", "NTRA", ["natera inc"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Invitae", "NVTA", ["invitae corporation"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Myriad Genetics", "MYGN", ["myriad genetics inc"], market_cap_bucket="small"),
            CompanyMapping("Veracyte", "VCYT", ["veracyte inc"], market_cap_bucket="small"),
            CompanyMapping("NeoGenomics", "NEO", ["neogenomics laboratories"], market_cap_bucket="small"),
            CompanyMapping("Exact Sciences", "EXAS", ["exact sciences corporation"], market_cap_bucket="mid"),
            CompanyMapping("CareDx", "CDNA", ["caredx inc"], market_cap_bucket="small"),
            CompanyMapping("Certara", "CERT", ["certara inc"], market_cap_bucket="mid"),
            CompanyMapping("Medpace", "MEDP", ["medpace holdings inc"], market_cap_bucket="mid"),
            CompanyMapping("IQVIA", "IQV", ["iqvia holdings inc"], market_cap_bucket="large"),
            # CompanyMapping("Syneos Health", "SYNH", [...]) — taken private 2023, removed
            CompanyMapping("TMO", "PPD", ["ppd inc"], market_cap_bucket="mid", parent_company="Thermo Fisher"),
            CompanyMapping("Charles River Laboratories", "CRL", ["charles river laboratories"], market_cap_bucket="mid"),
            CompanyMapping("ICON", "ICLR", ["icon plc"], market_cap_bucket="mid"),
            CompanyMapping("PRA Health Sciences", "ICLR", ["pra health sciences"], market_cap_bucket="mid", parent_company="ICON"),
            CompanyMapping("Thermo Fisher Scientific", "TMO", ["thermo fisher scientific inc"], market_cap_bucket="large"),
            CompanyMapping("Danaher", "DHR", ["danaher corporation"], market_cap_bucket="large"),
            CompanyMapping("Agilent Technologies", "A", ["agilent technologies inc"], market_cap_bucket="large"),
            CompanyMapping("Waters Corporation", "WAT", ["waters corporation"], market_cap_bucket="mid"),
            CompanyMapping("Mettler-Toledo", "MTD", ["mettler-toledo international"], market_cap_bucket="mid"),
            CompanyMapping("PerkinElmer", "RVTY", ["perkinelmer inc", "revvity"], market_cap_bucket="mid"),
            CompanyMapping("Bio-Rad Laboratories", "BIO", ["bio-rad laboratories"], market_cap_bucket="mid"),
            CompanyMapping("Illumina", "ILMN", ["illumina inc"], market_cap_bucket="mid"),
            CompanyMapping("Qiagen", "QGEN", ["qiagen nv"], market_cap_bucket="mid"),
            CompanyMapping("Labcorp", "LH", ["laboratory corporation of america", "labcorp"], market_cap_bucket="mid"),
            CompanyMapping("Quest Diagnostics", "DGX", ["quest diagnostics incorporated"], market_cap_bucket="mid"),
            CompanyMapping("Becton Dickinson", "BDX", ["becton dickinson and company", "bd"], market_cap_bucket="large"),
            CompanyMapping("Dexcom", "DXCM", ["dexcom inc"], market_cap_bucket="large"),
            CompanyMapping("Insulet", "PODD", ["insulet corporation"], market_cap_bucket="mid"),
            CompanyMapping("Tandem Diabetes Care", "TNDM", ["tandem diabetes care inc"], market_cap_bucket="mid"),
            CompanyMapping("Abbott Laboratories", "ABT", ["abbott laboratories"], market_cap_bucket="large"),
            CompanyMapping("Medtronic", "MDT", ["medtronic plc"], market_cap_bucket="large"),
            CompanyMapping("Boston Scientific", "BSX", ["boston scientific corporation"], market_cap_bucket="large"),
            CompanyMapping("Edwards Lifesciences", "EW", ["edwards lifesciences corporation"], market_cap_bucket="large"),
            CompanyMapping("Intuitive Surgical", "ISRG", ["intuitive surgical inc"], market_cap_bucket="large"),
            CompanyMapping("Stryker", "SYK", ["stryker corporation"], market_cap_bucket="large"),
            CompanyMapping("Zimmer Biomet", "ZBH", ["zimmer biomet holdings"], market_cap_bucket="mid"),
            CompanyMapping("Smith & Nephew", "SNN", ["smith & nephew plc"], market_cap_bucket="mid"),
            CompanyMapping("ResMed", "RMD", ["resmed inc"], market_cap_bucket="large"),
            CompanyMapping("Philips", "PHG", ["koninklijke philips nv", "royal philips"], market_cap_bucket="large"),
            CompanyMapping("Siemens Healthineers", "SHL.DE", ["siemens healthineers ag"], market_cap_bucket="large"),
            CompanyMapping("GE HealthCare", "GEHC", ["ge healthcare technologies"], market_cap_bucket="large"),
            CompanyMapping("Hologic", "HOLX", ["hologic inc"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Varian Medical", "VAR", ["varian medical systems"], market_cap_bucket="mid", parent_company="Siemens"),  # delisted/acquired
            CompanyMapping("Masimo", "MASI", ["masimo corporation"], market_cap_bucket="mid"),
            CompanyMapping("Penumbra", "PEN", ["penumbra inc"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Inari Medical", "NARI", ["inari medical inc"], market_cap_bucket="mid"),  # delisted/acquired
            CompanyMapping("Shockwave Medical", "JNJ", ["shockwave medical inc"], market_cap_bucket="mid", parent_company="Johnson & Johnson"),
            CompanyMapping("Novocure", "NVCR", ["novocure ltd"], market_cap_bucket="mid"),
            CompanyMapping("Glaukos", "GKOS", ["glaukos corporation"], market_cap_bucket="mid"),
            CompanyMapping("STAAR Surgical", "STAA", ["staar surgical company"], market_cap_bucket="small"),
            CompanyMapping("Axonics", "BSX", ["axonics inc"], market_cap_bucket="mid"),
            # REMOVED: CompanyMapping("Nevro", "NVRO", ["nevro corporation"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("Intersect ENT", "MDT", ["intersect ent inc"], market_cap_bucket="small", parent_company="Medtronic"),
            CompanyMapping("Acclarent", "ACCL", ["acclarent inc"], market_cap_bucket="small", parent_company="Johnson & Johnson"),
            # REMOVED: CompanyMapping("Auris Health", "AURS", ["auris health inc"], market_cap_bucket="private", parent_company="Johnson & Johnson"),  # delisted/acquired
            # REMOVED: CompanyMapping("Verb Surgical", "VERB", ["verb surgical"], market_cap_bucket="private", parent_company="Johnson & Johnson"),  # delisted/acquired
            CompanyMapping("Orthopediatrics", "KIDS", ["orthopediatrics corporation"], market_cap_bucket="small"),
            # REMOVED: CompanyMapping("SeaSpine", "SPNE", ["seaspine holdings corporation"], market_cap_bucket="small"),  # delisted/acquired
            CompanyMapping("K2M Group Holdings", "SYK", ["k2m group holdings"], market_cap_bucket="small", parent_company="Stryker"),
            CompanyMapping("Mazor Robotics", "MDT", ["mazor robotics"], market_cap_bucket="small", parent_company="Medtronic"),
            # REMOVED: CompanyMapping("Titan Medical", "TMDI", ["titan medical inc"], market_cap_bucket="micro"),  # delisted/acquired
            # REMOVED: CompanyMapping("TransEnterix", "TRXC", ["transenterix inc", "asensus surgical"], market_cap_bucket="micro"),  # delisted/acquired
            CompanyMapping("Vicarious Surgical", "RBOT", ["vicarious surgical inc"], market_cap_bucket="micro"),
            # REMOVED: CompanyMapping("Memic Innovative Surgery", "MEMC", ["memic innovative surgery"], market_cap_bucket="private"),  # delisted/acquired
            # REMOVED: CompanyMapping("CMR Surgical", "CMR", ["cmr surgical"], market_cap_bucket="private"),  # delisted/acquired
            # REMOVED: CompanyMapping("Avatera Medical", "AVAT", ["avatera medical"], market_cap_bucket="private"),  # delisted/acquired
            # REMOVED: CompanyMapping("Distalmotion", "DIST", ["distalmotion"], market_cap_bucket="private"),  # delisted/acquired
            # REMOVED: CompanyMapping("Momentis Surgical", "MOMS", ["momentis surgical"], market_cap_bucket="private"),  # delisted/acquired
        ]
        
        for company in companies:
            self._add_mapping(company)
        
        logger.info(f"Initialized {len(self._mappings)} company mappings")
    
    def _add_mapping(self, mapping: CompanyMapping):
        """Add a company mapping."""
        canonical_name = mapping.name.lower()
        self._mappings[canonical_name] = mapping
        self._ticker_to_name[mapping.ticker] = canonical_name
        
        # Add aliases
        self._alias_map[canonical_name] = canonical_name
        for alias in mapping.aliases:
            self._alias_map[alias.lower()] = canonical_name
    
    def get_ticker(self, company_name: str) -> Optional[str]:
        """Get ticker for a company name with fuzzy matching."""
        if not company_name:
            return None
        
        # Check cache
        cache_key = company_name.lower()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Direct lookup
        name_lower = company_name.lower()
        if name_lower in self._alias_map:
            canonical = self._alias_map[name_lower]
            ticker = self._mappings[canonical].ticker
            self._cache[cache_key] = ticker
            return ticker
        
        # Fuzzy matching
        best_match = None
        best_score = 0
        
        for alias, canonical in self._alias_map.items():
            score = SequenceMatcher(None, name_lower, alias).ratio()
            if score > best_score and score >= self._fuzzy_threshold:
                best_score = score
                best_match = canonical
        
        if best_match:
            ticker = self._mappings[best_match].ticker
            self._cache[cache_key] = ticker
            logger.debug(f"Fuzzy match: '{company_name}' -> '{best_match}' (score: {best_score:.2f})")
            return ticker
        
        self._cache[cache_key] = None
        return None
    
    def get_company_name(self, ticker: str) -> Optional[str]:
        """Get company name from ticker."""
        ticker_upper = ticker.upper()
        if ticker_upper in self._ticker_to_name:
            canonical = self._ticker_to_name[ticker_upper]
            return self._mappings[canonical].name
        return None
    
    def get_company_info(self, ticker: str) -> Optional[CompanyMapping]:
        """Get full company mapping info."""
        ticker_upper = ticker.upper()
        if ticker_upper in self._ticker_to_name:
            canonical = self._ticker_to_name[ticker_upper]
            return self._mappings[canonical]
        return None
    
    def find_companies_by_pattern(self, pattern: str) -> List[Tuple[str, str]]:
        """Find companies matching a pattern."""
        pattern_lower = pattern.lower()
        matches = []
        
        for name, mapping in self._mappings.items():
            if pattern_lower in name or any(pattern_lower in alias for alias in mapping.aliases):
                matches.append((mapping.name, mapping.ticker))
        
        return matches
    
    def get_all_tickers(self) -> List[str]:
        """Get all tracked tickers."""
        return list(self._ticker_to_name.keys())
    
    def get_tickers_by_market_cap(self, bucket: str) -> List[str]:
        """Get tickers filtered by market cap bucket."""
        return [
            m.ticker for m in self._mappings.values()
            if m.market_cap_bucket == bucket
        ]
    
    def add_company(self, mapping: CompanyMapping):
        """Add a new company mapping dynamically."""
        self._add_mapping(mapping)
        logger.info(f"Added company mapping: {mapping.name} -> {mapping.ticker}")


# Singleton instance
_mapper: Optional[CompanyMapper] = None


def get_company_mapper() -> CompanyMapper:
    """Get singleton instance of CompanyMapper."""
    global _mapper
    if _mapper is None:
        _mapper = CompanyMapper()
    return _mapper
