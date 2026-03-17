"""Tests for company mapper."""

import pytest
from src.data_sources.company_mapper import CompanyMapper, get_company_mapper


class TestCompanyMapper:
    """Test cases for CompanyMapper."""
    
    def test_singleton(self):
        """Test that get_company_mapper returns singleton."""
        mapper1 = get_company_mapper()
        mapper2 = get_company_mapper()
        assert mapper1 is mapper2
    
    def test_exact_match(self):
        """Test exact company name matching."""
        mapper = CompanyMapper()
        
        assert mapper.get_ticker("Pfizer") == "PFE"
        assert mapper.get_ticker("Moderna") == "MRNA"
        assert mapper.get_ticker("Vertex Pharmaceuticals") == "VRTX"
    
    def test_alias_match(self):
        """Test alias matching."""
        mapper = CompanyMapper()
        
        assert mapper.get_ticker("pfizer inc") == "PFE"
        assert mapper.get_ticker("pfizer pharmaceuticals") == "PFE"
        assert mapper.get_ticker("moderna tx") == "MRNA"
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        mapper = CompanyMapper()
        
        assert mapper.get_ticker("PFIZER") == "PFE"
        assert mapper.get_ticker("pfizer") == "PFE"
        assert mapper.get_ticker("PfIzEr") == "PFE"
    
    def test_unknown_company(self):
        """Test handling of unknown companies."""
        mapper = CompanyMapper()
        
        assert mapper.get_ticker("Unknown Company XYZ") is None
        assert mapper.get_ticker("") is None
    
    def test_get_company_info(self):
        """Test retrieving full company info."""
        mapper = CompanyMapper()
        
        info = mapper.get_company_info("PFE")
        assert info is not None
        assert info.ticker == "PFE"
        assert info.name == "Pfizer"
        assert "pfizer inc" in info.aliases
    
    def test_find_by_pattern(self):
        """Test pattern matching."""
        mapper = CompanyMapper()
        
        results = mapper.find_companies_by_pattern("pharma")
        assert len(results) > 0
        
        # Check that all results contain the pattern
        for name, ticker in results:
            assert "pharma" in name.lower() or any("pharma" in alias for alias in mapper.get_company_info(ticker).aliases)
    
    def test_get_all_tickers(self):
        """Test getting all tickers."""
        mapper = CompanyMapper()
        
        tickers = mapper.get_all_tickers()
        assert len(tickers) > 200
        assert "PFE" in tickers
        assert "MRNA" in tickers
    
    def test_market_cap_filter(self):
        """Test filtering by market cap bucket."""
        mapper = CompanyMapper()
        
        large_caps = mapper.get_tickers_by_market_cap("large")
        small_caps = mapper.get_tickers_by_market_cap("small")
        
        assert "PFE" in large_caps
        assert "JNJ" in large_caps
        assert len(small_caps) > 0
    
    def test_add_company(self):
        """Test dynamically adding a company."""
        mapper = CompanyMapper()
        
        from src.data_sources.company_mapper import CompanyMapping
        
        new_company = CompanyMapping(
            name="Test Biotech",
            ticker="TEST",
            aliases=["test biotech inc"],
            market_cap_bucket="small"
        )
        
        mapper.add_company(new_company)
        
        assert mapper.get_ticker("Test Biotech") == "TEST"
        assert mapper.get_ticker("test biotech inc") == "TEST"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
