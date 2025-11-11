# Data Sources Research

## Current Status

### ✅ Albuquerque (Bernalillo County)
**Status:** WORKING  
**Source:** City of Albuquerque Environmental Health  
**Format:** Weekly PDF reports  
**URL:** https://www.cabq.gov/environmentalhealth/documents/chpd_main_inspection_report.pdf  
**Coverage:** 88 inspections from 5 weeks (Sept 21 - Nov 1, 2025)  
**Data Quality:** Excellent - includes violations, operational status, dates

**Historical PDFs:**
- `chpd_main_inspection_report.pdf` (current week)
- `media-report-10-19-10-25.pdf`
- `media-report-10-5-10-11.pdf`  
- `media-report-9-28-10-04.pdf`
- `media-report-9-21-9-27.pdf`

---

## Remaining 9 Cities - NMED Coverage

All other cities are covered by the **New Mexico Environment Department (NMED) Food Safety Program**.

### 🔍 NMED API Portal (Registration Required)

**URL:** https://api.env.nm.gov/  
**Status:** Requires account registration  
**Process:**
1. Register at https://api.env.nm.gov/
2. Browse available APIs in the catalog
3. Look for food establishment inspection datasets
4. Request API key if needed

**Alternative:** Public Records Request at https://www.env.nm.gov/public-record-request/

---

## City Coverage Mapping

| City | County | Population | Data Source | Status |
|------|--------|------------|-------------|---------|
| **Albuquerque** | Bernalillo | 560,000+ | City PDFs | ✅ Working |
| Las Cruces | Doña Ana | 111,000+ | NMED | ⏸️ Pending API |
| Rio Rancho | Sandoval | 104,000+ | NMED | ⏸️ Pending API |
| Santa Fe | Santa Fe | 87,000+ | NMED | ⏸️ Pending API |
| Roswell | Chaves | 48,000+ | NMED | ⏸️ Pending API |
| Farmington | San Juan | 46,000+ | NMED | ⏸️ Pending API |
| Hobbs | Lea | 40,000+ | NMED | ⏸️ Pending API |
| Clovis | Curry | 39,000+ | NMED | ⏸️ Pending API |
| Carlsbad | Eddy | 32,000+ | NMED | ⏸️ Pending API |
| Alamogordo | Otero | 31,000+ | NMED | ⏸️ Pending API |

---

## Next Steps

### Option 1: NMED API Portal (Checked - No Food Data) ❌
**Status:** NMED API portal does NOT include food inspection data  
**Available APIs:** Air Quality, Water Quality, Waste Management only  
**Conclusion:** Food inspection data not publicly available via API

### Option 1B: Contact NMED Food Safety Program (Recommended) ✅
1. Email: NMED.Food.Program@env.nm.gov
2. Phone: (505) 827-2821
3. Request: Bulk data export or API access for restaurant inspections
4. Ask for: Establishments with conditional/failed/closed status, past 6 months
5. Format preference: JSON, CSV, or database dump

### Option 2: Public Records Request
1. Submit request at https://www.env.nm.gov/public-record-request/
2. Request: "Restaurant health inspection records for [cities] from past 12 months"
3. Receive bulk data export
4. Import into system

### Option 3: Individual County Research ❌
**Status:** Researched - No municipal/county data portals found  
**Findings:**
- Las Cruces: No public inspection database
- Santa Fe: No city/county inspection portal
- Rio Rancho: No municipal health inspection data
- Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo: No public portals

**Conclusion:** All 9 cities defer to NMED Food Safety Program for inspections. Only Albuquerque manages its own system.

### Option 4: Manual Entry (Initial Dataset)
- Request NMED for recent closure/conditional approval list
- Manually add high-priority restaurants to seed dataset

---

## Data Format Requirements

To integrate NMED data with existing ABQ structure, we need:

**Required Fields:**
- Establishment name
- Address
- City
- Inspection date (YYYY-MM-DD)
- Inspection outcome (approved/conditional/failed/closed)
- Operational status (Open/Closed)

**Optional Fields:**
- Violations list (array of descriptions)
- Permit number
- Inspection type
- Geocoordinates

**Current Parser:** `scripts/fetch_nmed.py` has placeholder code for both:
- ArcGIS FeatureServer endpoint
- REST API (Apigee) endpoint

Once endpoint URLs are known, minimal code changes needed.

---

## Recommended Action Plan

**Immediate (BEST PATH FORWARD):**
1. ✅ Contact NMED Food Safety Program via email
   - Email: NMED.Food.Program@env.nm.gov
   - Use template in NMED_REQUEST.md
   - Request bulk data export for 9 cities
2. Ask specifically for establishments with violations (skip approved-only)
3. Request format: CSV or JSON preferred
4. Mention it's for public service aggregation project

**Short-term (Once Data Received):**
1. Parse NMED data format (likely CSV or PDF)
2. Map to existing schema (match ABQ structure)
3. Update `fetch_nmed.py` or create `parse_nmed_export.py`
4. Merge with ABQ data in pipeline
5. Deploy to site

**Alternative (If NMED Unresponsive):**
- Focus on expanding ABQ historical data (more weeks back)
- Consider manual entry of high-priority closures from NMED website
- Wait for NMED to publish open data portal

**Ongoing:**
- ✅ Monitor ABQ PDFs weekly (automated via GitHub Actions)
- Add NMED data refresh when available
- Nightly pipeline runs will merge both sources

---

## Notes

- ABQ handles its own inspections (Bernalillo County excluded from NMED)
- NMED Food Safety Program: https://www.env.nm.gov/foodprogram/
- Current data: Albuquerque only, but system ready for statewide expansion
- Parser architecture supports multiple sources (NMED + ABQ)
