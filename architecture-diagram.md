# EcoSentinel AI — System Architecture Diagram

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_snc_ecosentine_0_`  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

## 1. High-Level Architecture

The following diagram illustrates the end-to-end data flow from the citizen reporting an incident to the AI processing it, and finally to the field inspector and legal compliance team resolving the issue.

```mermaid
graph TD
    %% Define styles
    classDef snApp fill:#4c6270,stroke:#fff,stroke-width:2px,color:#fff
    classDef userPortal fill:#5f9ea0,stroke:#fff,stroke-width:2px,color:#fff
    classDef mobileApp fill:#00b4d8,stroke:#fff,stroke-width:2px,color:#fff
    classDef externalAPI fill:#f4a261,stroke:#fff,stroke-width:2px,color:#fff
    classDef aiAgent fill:#e76f51,stroke:#fff,stroke-width:2px,color:#fff
    
    %% Actors
    Citizen([Citizen])
    Inspector([Field Inspector])
    Officer([Compliance Officer])
    
    %% Channels
    subgraph "Channels & UI"
        Portal[Service Portal]:::userPortal
        Tracker[Tracker Widget]:::userPortal
        VA[Virtual Agent]:::userPortal
        NowMobile[Now Mobile App]:::mobileApp
        Workspace[Officer Workspace]:::snApp
    end
    
    %% ServiceNow Core Tables & Flows
    subgraph "ServiceNow Platform (x_snc_ecosentine_0_)"
        Complaint[(x_snc_ecosentine_0_complaint)]:::snApp
        Facility[(x_snc_ecosentine_0_facility)]:::snApp
        Inspection[(x_snc_ecosentine_0_inspection)]:::snApp
        Finding[(x_snc_ecosentine_0_finding)]:::snApp
        LegalCase[(x_snc_ecosentine_0_legal_case)]:::snApp
        AgentLog[(x_snc_ecosentine_0_agent_decisi)]:::snApp
        
        FL01[FL-01: AI Webhook Dispatch]
        FL02[FL-02: Fallback Timer]
        FL03[FL-03: Inspector Dispatch]
        FL05[FL-05: Legal Case Creation]
        
        BR_C01[BR-C01: Defaults]
        BR_C03[BR-C03: AI Write-back]
    end
    
    %% External Integration
    subgraph "FastAPI Microservice"
        FastAPI[Python Integration Layer]:::externalAPI
        TriageAgent[Triage Agent]:::aiAgent
        VisionAgent[OpenAI GPT-4o Vision]:::aiAgent
        FusionAgent[Severity Fusion Agent]:::aiAgent
    end
    
    %% Native AI Agents
    subgraph "Now Assist Agents"
        ReportAgent[Inspection Report Agent]:::aiAgent
        SummaryAgent[Legal Summary Agent]:::aiAgent
        InsightsAgent[Leadership Insights Agent]:::aiAgent
    end
    
    %% Flow mapping
    Citizen -->|Submit Report| Portal
    Citizen -->|Check Status| Tracker
    Citizen -->|Chat| VA
    
    Portal -->|Insert| Complaint
    BR_C01 -.->|Auto-Num| Complaint
    Complaint -->|Trigger| FL01
    
    FL01 -->|POST Webhook| FastAPI
    FastAPI -->|Extract Image| VisionAgent
    FastAPI -->|Extract Text| TriageAgent
    VisionAgent --> FusionAgent
    TriageAgent --> FusionAgent
    
    FusionAgent -->|PATCH Severity & Rationale| Complaint
    FastAPI -->|POST Log| AgentLog
    
    Complaint -->|Triggers| BR_C03
    BR_C03 -->|State Advance| Complaint
    Complaint -->|State = AI Verified| FL03
    
    FL03 -->|Create & Assign| Inspection
    Inspection -->|Assigned To| NowMobile
    Inspector -->|Log Evidence| NowMobile
    NowMobile -->|Update| Inspection
    NowMobile -->|Insert| Finding
    
    Inspection -->|Trigger| ReportAgent
    ReportAgent -->|Generate Report| Inspection
    
    Inspection -->|Violation Confirmed| FL05
    FL05 -->|Create| LegalCase
    LegalCase -->|Link to| Facility
    
    FL05 -->|Trigger| SummaryAgent
    SummaryAgent -->|Write Narrative| LegalCase
    
    Officer -->|Review & Action| Workspace
    Workspace -->|Read/Write| Complaint
    Workspace -->|Read/Write| Inspection
    Workspace -->|Read/Write| LegalCase
```

## 2. Component Breakdown

* **Channels**: Citizens report incidents via the **Service Portal** (PWA). Inspectors execute fieldwork via **Now Mobile**. Officers and Legal Handlers manage the backend via the **Officer Workspace**.
* **AI Integration**: The platform offloads complex multi-modal reasoning to an external **FastAPI Microservice** which orchestrates OpenAI's **GPT-4o Vision API** for photo analysis and LLMs for text triage. 
* **Native AI Agents**: ServiceNow's native **AI Agent Studio** is used for structured internal tasks like summarizing inspection reports and drafting legal narratives.
* **Core Tables**: 
  * `x_snc_ecosentine_0_complaint` (Intake)
  * `x_snc_ecosentine_0_inspection` & `x_snc_ecosentine_0_finding` (Fieldwork)
  * `x_snc_ecosentine_0_legal_case` (Enforcement)
  * `x_snc_ecosentine_0_facility` (Compliance Registry)
  * `x_snc_ecosentine_0_agent_decisi` (Immutable Audit Trail)
* **Automation**: Flow Designer handles all asynchronous routing, SLAs, fallback timers, and citizen notifications. Business Rules enforce immutability, state regression blocks, and synchronous data validation.
