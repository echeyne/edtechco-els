# Ground Truth Annotations

Place human-annotated ground truth files here, one per state document.

## File Format

Each file should be named `{state}.json` (e.g., `TX.json`, `CA.json`) and contain:

```json
{
  "state": "TX",
  "country": "US",
  "version_year": 2024,
  "source_document": "texas_prek_guidelines_2024.pdf",
  "annotator": "your_name",
  "annotation_date": "2026-04-27",
  "elements": [
    {
      "level": "domain",
      "code": "I",
      "title": "Social and Emotional Development",
      "description": "...",
      "source_page": 5
    },
    {
      "level": "strand",
      "code": "A",
      "title": "Self-Concept",
      "description": "...",
      "parent_code": "I",
      "source_page": 5
    },
    {
      "level": "indicator",
      "code": "I.A.1",
      "title": "Child is aware of where own body is in space...",
      "description": "...",
      "parent_code": "A",
      "domain_code": "I",
      "strand_code": "A",
      "sub_strand_code": null,
      "age_band": "48-60",
      "source_page": 6
    }
  ]
}
```

## Annotation Guidelines

1. Read the full PDF and identify every structural element
2. Classify by nesting depth (same rules as the pipeline):
   - Depth 1 = domain, Depth 2 = strand, Depth 3 = sub_strand, Depth 4 = indicator
3. Record the exact code, title, and description from the document
4. For indicators, record the full parent chain (domain_code, strand_code, sub_strand_code)
5. Record age_band in months format (e.g., "36-48", "48-60")
6. Include source_page for traceability

## Recommended States to Annotate

Pick 3-5 states that represent different document structures:

| State | Why                                         | Structure                    |
| ----- | ------------------------------------------- | ---------------------------- |
| TX    | Side-by-side PK3/PK4 age columns            | 4-level with age variants    |
| CA    | Clean hierarchy, well-structured            | 4-level standard             |
| OH    | 3-level (no sub_strand)                     | 3-level                      |
| SC    | Unusual terminology ("Domains of Learning") | 4-level, non-standard labels |
| NY    | Dense, many indicators                      | 4-level, high volume         |
