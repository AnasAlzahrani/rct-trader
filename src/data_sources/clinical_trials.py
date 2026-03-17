"""Enhanced ClinicalTrials.gov API client with caching and retry logic."""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache
import json
from loguru import logger

from src.utils.config import settings


@dataclass
class TrialData:
    """Structured trial data."""
    nct_id: str
    brief_title: str
    official_title: Optional[str]
    phase: Optional[str]
    overall_status: str
    conditions: List[str]
    interventions: List[str]
    sponsor: Optional[str]
    collaborators: List[str]
    enrollment_count: Optional[int]
    study_start_date: Optional[datetime]
    primary_completion_date: Optional[datetime]
    completion_date: Optional[datetime]
    first_posted_date: Optional[datetime]
    results_first_posted_date: Optional[datetime]
    last_update_posted_date: Optional[datetime]
    has_results: bool
    study_type: Optional[str]
    allocation: Optional[str]
    intervention_model: Optional[str]
    primary_purpose: Optional[str]
    masking: Optional[str]
    raw_data: Dict[str, Any]


class ClinicalTrialsClient:
    """Client for ClinicalTrials.gov API v2."""
    
    BASE_URL = settings.CLINICAL_TRIALS_BASE_URL
    RATE_LIMIT = settings.CLINICAL_TRIALS_RATE_LIMIT
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={
                "Accept": "application/json",
                "User-Agent": f"RCT-Trader/{settings.APP_VERSION}"
            }
        )
        self._cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour cache
        self._last_request_time = 0
        self._semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # Don't close - client is reused across scans
    
    async def close(self):
        """Explicitly close the client when done."""
        await self.client.aclose()
    
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        import time
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.RATE_LIMIT:
            await asyncio.sleep(self.RATE_LIMIT - time_since_last)
        self._last_request_time = time.time()
    
    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make rate-limited API request with retry logic."""
        async with self._semaphore:
            await self._rate_limit()
            
            url = f"{self.BASE_URL}/{endpoint}"
            cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
            
            # Check cache
            if cache_key in self._cache:
                logger.debug(f"Cache hit for {endpoint}")
                return self._cache[cache_key]
            
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Cache successful response
                self._cache[cache_key] = data
                return data
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
                if e.response.status_code == 429:
                    # Rate limited - wait longer
                    await asyncio.sleep(5)
                raise
            except Exception as e:
                logger.error(f"Error requesting {url}: {e}")
                raise
    
    async def search_studies(
        self,
        query: Optional[str] = None,
        sponsor: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        posted_date_from: Optional[datetime] = None,
        posted_date_to: Optional[datetime] = None,
        limit: int = 100,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for studies with various filters using CT.gov API v2."""
        params = {"pageSize": min(limit, 100)}
        
        if query:
            params["query.term"] = query
        
        # Build filter.advanced with AREA syntax
        filters = []
        if sponsor:
            filters.append(f'AREA[LeadSponsorName]"{sponsor}"')
        if phase:
            # phase can be "PHASE2 OR PHASE3 OR PHASE4"
            filters.append(f"AREA[Phase]({phase})")
        if status:
            filters.append(f'AREA[OverallStatus]{status}')
        if posted_date_from:
            date_str = posted_date_from.strftime("%m/%d/%Y")
            filters.append(f"AREA[LastUpdatePostDate]RANGE[{date_str},MAX]")
        if posted_date_to:
            date_str = posted_date_to.strftime("%m/%d/%Y")
            filters.append(f"AREA[LastUpdatePostDate]RANGE[MIN,{date_str}]")
        if start_date_from:
            date_str = start_date_from.strftime("%m/%d/%Y")
            filters.append(f"AREA[StartDate]RANGE[{date_str},MAX]")
        
        if filters:
            params["filter.advanced"] = " AND ".join(filters)
        
        if page_token:
            params["pageToken"] = page_token
        
        return await self._make_request("studies", params)
    
    async def get_study(self, nct_id: str) -> Optional[TrialData]:
        """Get detailed information about a specific study."""
        try:
            data = await self._make_request(f"studies/{nct_id}")
            return self._parse_study(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Study {nct_id} not found")
                return None
            raise
    
    async def get_studies_by_sponsor(
        self, 
        sponsor: str, 
        days_back: int = 30
    ) -> List[TrialData]:
        """Get all studies for a specific sponsor."""
        posted_from = datetime.now() - timedelta(days=days_back)
        
        studies = []
        page_token = None
        
        while True:
            response = await self.search_studies(
                sponsor=sponsor,
                posted_date_from=posted_from,
                limit=100,
                page_token=page_token
            )
            
            for study_data in response.get("studies", []):
                parsed = self._parse_study(study_data)
                if parsed:
                    studies.append(parsed)
            
            # Check for next page
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        
        logger.info(f"Found {len(studies)} studies for sponsor {sponsor}")
        return studies
    
    async def get_recent_updates(
        self, 
        hours: int = 24,
        min_phase: str = "PHASE2"
    ) -> AsyncGenerator[TrialData, None]:
        """Stream recent trial updates."""
        posted_from = datetime.now() - timedelta(hours=hours)
        
        # Build phase filter
        phase_filter = None
        if min_phase:
            phases = {"PHASE2": ["PHASE2", "PHASE3", "PHASE4"],
                      "PHASE3": ["PHASE3", "PHASE4"],
                      "PHASE4": ["PHASE4"]}
            phase_list = phases.get(min_phase, [min_phase])
            phase_filter = " OR ".join(phase_list)
        
        page_token = None
        while True:
            response = await self.search_studies(
                posted_date_from=posted_from,
                phase=phase_filter,
                limit=100,
                page_token=page_token
            )
            
            for study_data in response.get("studies", []):
                parsed = self._parse_study(study_data)
                if parsed:
                    yield parsed
            
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    
    async def get_studies_with_results(
        self,
        days_back: int = 7,
        sponsor: Optional[str] = None
    ) -> List[TrialData]:
        """Get studies that recently posted results."""
        posted_from = datetime.now() - timedelta(days=days_back)
        
        studies = []
        page_token = None
        
        while True:
            date_str = posted_from.strftime("%m/%d/%Y")
            filters = [f"AREA[ResultsFirstPostDate]RANGE[{date_str},MAX]"]
            if sponsor:
                filters.append(f'AREA[LeadSponsorName]"{sponsor}"')
            
            params = {
                "pageSize": 100,
                "filter.advanced": " AND ".join(filters)
            }
            if page_token:
                params["pageToken"] = page_token
            
            response = await self._make_request("studies", params)
            
            for study_data in response.get("studies", []):
                parsed = self._parse_study(study_data)
                if parsed and parsed.has_results:
                    studies.append(parsed)
            
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        
        return studies
    
    def _parse_study(self, data: Dict[str, Any]) -> Optional[TrialData]:
        """Parse raw API response into structured TrialData."""
        try:
            protocol = data.get("protocolSection", {})
            results = data.get("resultsSection", {})
            derived = data.get("derivedSection", {})
            
            # Identification
            id_info = protocol.get("identificationModule", {})
            nct_id = id_info.get("nctId")
            if not nct_id:
                return None
            
            brief_title = id_info.get("briefTitle", "")
            official_title = id_info.get("officialTitle")
            
            # Status
            status_module = protocol.get("statusModule", {})
            overall_status = status_module.get("overallStatus", "UNKNOWN")
            
            # Dates
            start_date = self._parse_date(status_module.get("startDateStruct", {}).get("date"))
            primary_completion = self._parse_date(status_module.get("primaryCompletionDateStruct", {}).get("date"))
            completion_date = self._parse_date(status_module.get("completionDateStruct", {}).get("date"))
            first_posted = self._parse_date(status_module.get("studyFirstPostDateStruct", {}).get("date"))
            results_posted = self._parse_date(status_module.get("resultsFirstPostDateStruct", {}).get("date"))
            last_update = self._parse_date(status_module.get("lastUpdatePostDateStruct", {}).get("date"))
            
            # Design
            design = protocol.get("designModule", {})
            phase = self._parse_phases(design.get("phases", []))
            study_type = design.get("studyType")
            enrollment = design.get("enrollmentInfo", {}).get("count")
            
            # More design details
            design_info = design.get("designInfo", {})
            allocation = design_info.get("allocation")
            intervention_model = design_info.get("interventionModel")
            primary_purpose = design_info.get("primaryPurpose")
            masking = self._parse_masking(design_info.get("maskingInfo", {}))
            
            # Sponsor
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name")
            collaborators = [c.get("name") for c in sponsor_module.get("collaborators", []) if c.get("name")]
            
            # Conditions and interventions
            conditions = derived.get("conditionBrowseModule", {}).get("meshes", [])
            condition_list = [c.get("term") for c in conditions if c.get("term")]
            if not condition_list:
                condition_list = protocol.get("conditionsModule", {}).get("conditions", [])
            
            interventions = protocol.get("armsInterventionsModule", {}).get("interventions", [])
            intervention_list = []
            for i in interventions:
                name = i.get("name", "")
                itype = i.get("type", "")
                if name:
                    intervention_list.append(f"{itype}: {name}" if itype else name)
            
            # Results
            has_results = bool(results)
            
            return TrialData(
                nct_id=nct_id,
                brief_title=brief_title,
                official_title=official_title,
                phase=phase,
                overall_status=overall_status,
                conditions=condition_list,
                interventions=intervention_list,
                sponsor=lead_sponsor,
                collaborators=collaborators,
                enrollment_count=enrollment,
                study_start_date=start_date,
                primary_completion_date=primary_completion,
                completion_date=completion_date,
                first_posted_date=first_posted,
                results_first_posted_date=results_posted,
                last_update_posted_date=last_update,
                has_results=has_results,
                study_type=study_type,
                allocation=allocation,
                intervention_model=intervention_model,
                primary_purpose=primary_purpose,
                masking=masking,
                raw_data=data
            )
            
        except Exception as e:
            logger.error(f"Error parsing study data: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string in various formats."""
        if not date_str:
            return None
        
        formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    def _parse_phases(self, phases: List[str]) -> Optional[str]:
        """Parse phase list into single phase."""
        if not phases:
            return None
        if len(phases) == 1:
            return phases[0]
        # Return highest phase for combined phases
        phase_order = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"]
        highest = None
        highest_idx = -1
        for phase in phases:
            try:
                idx = phase_order.index(phase)
                if idx > highest_idx:
                    highest_idx = idx
                    highest = phase
            except ValueError:
                continue
        return highest
    
    def _parse_masking(self, masking_info: Dict[str, Any]) -> Optional[str]:
        """Parse masking information."""
        if not masking_info:
            return None
        
        masking = masking_info.get("masking")
        if masking:
            return masking
        
        # Check for specific masks
        who_masked = masking_info.get("whoMasked", [])
        if who_masked:
            return f"Masked: {', '.join(who_masked)}"
        
        return None
    
    async def get_trial_history(self, nct_id: str) -> List[Dict[str, Any]]:
        """Get version history for a trial."""
        try:
            data = await self._make_request(f"studies/{nct_id}/history")
            return data.get("versions", [])
        except Exception as e:
            logger.error(f"Error getting history for {nct_id}: {e}")
            return []


# Singleton instance
_ct_client: Optional[ClinicalTrialsClient] = None


def get_clinical_trials_client() -> ClinicalTrialsClient:
    """Get singleton instance of ClinicalTrialsClient."""
    global _ct_client
    if _ct_client is None:
        _ct_client = ClinicalTrialsClient()
    return _ct_client
