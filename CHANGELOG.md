# Changelog

All notable changes to ERPX AI Kế Toán will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-02-02

### Added
- **Agent Action Hub**: UI confirm/cancel flow cho Copilot actions
  - `ActionProposalCard` component
  - API endpoints: `/v1/agent/actions/*`
  - Database: `agent_action_proposals` table
  
- **Analyze Module**: Unified Reports + Data Analyst
  - Tab "Báo cáo": Pre-built reports
  - Tab "Data Analyze": Dataset upload + NL2SQL query
  - API endpoints: `/v1/analyze/*`
  - Database: `datasets` table
  
- **OCR Preview Overlay**:
  - Bounding boxes overlay trên document image
  - Fields panel với thông tin trích xuất
  - Hover highlight liên kết field ↔ box
  - API: `/v1/documents/{id}/ocr-boxes`, `/raw-vs-cleaned`
  - Database: `ocr_boxes` table

### Changed
- Navigation: Merge "Báo cáo" + "Data Analyst" thành "Analyze"
- `DocumentPreview` component: Enhanced với OCR overlay support
- `CopilotChat`: Extended để render action proposals

### Deprecated
- Route `/reports` → use `/analyze` (Tab Báo cáo)
- Route `/analyst` → use `/analyze` (Tab Data Analyze)

### Removed
- N/A

### Fixed
- TypeScript errors in `ApprovalsInbox`
- NL2SQL schema alignment với `extracted_invoices`

### Security
- N/A

---

## [1.0.0] - 2026-01-20

### Added
- Initial release
- Document upload & OCR extraction
- Journal proposal generation
- Multi-level approval workflow
- AI Copilot chat
- Evidence tracking & audit logs
- Keycloak authentication
- Temporal workflow orchestration

---

*For migration guides, see [docs/migrations/](docs/migrations/)*
