#!/usr/bin/env python3
"""
Run 50 RAG evaluation queries against the Flogo Weaviate RAG service
using the new LLM-assisted generation endpoint.

Flogo request:  POST /rag/weaviate/query/generate  { query, collection, topK }
Flogo response: { answer, formattedContext, sourceDocuments[], totalFound, duration }

The RAGQueryGenerate activity: embed → hybrid search → LLM answer (llama3.1:8b)
The Flogo app fires rageval events automatically via its SendRagevalEvent activity.

Collection: FlogoSmartDocs  (Flogo pipeline, Docling PDF parsing, LLM-assisted)
Compare against:
  BW6 pipeline  : collection=TikaTestDocs    (full RAG, BW6)
  Flogo pure    : collection=FlogoTestDocs   (retrieval only)
"""
import urllib.request, json, time

RAG        = "http://localhost:9191/rag/weaviate/query/generate"
RAGEVAL    = "http://localhost:9090/eval/v1/metrics"
import os
COLLECTION = os.environ.get("COLLECTION","FlogoSmartDocs")
TOP_K      = 3

# --------------------------------------------------------------------------
# Doc 1: Functional_Specs.pdf — 17486, SAP MDG → ContractPodAi CLM
# --------------------------------------------------------------------------
functional_queries = [
    # F1
    "What authentication method does the ContractPodAi API use?",
    # F2
    "What grant types are supported for generating the ContractPodAi auth token?",
    # F3
    "What is the Dev URL for the ContractPodAi authentication endpoint?",
    # F4
    "What is the API endpoint and HTTP method used for the Business Partner upsert operation?",
    # F5
    "What fields are required in the request body for creating a business partner client?",
    # F6
    "What is the unique identifier for a partner address record in ContractPodAi?",
    # F7
    "How many ContractPodAi tenants need to be configured and what are their names?",
    # F8
    "What is the scope of the Business Partner integration?",
    # F9
    "What protocol and message format are used for receiving data in this integration?",
    # F10
    "What is the external ID used for identifying business partners in the initial bulk upload?",
]

# --------------------------------------------------------------------------
# Doc 2: 1020882549 — 02 [9469] Interface Assessment, LS Central POS → SAP S/4 HANA
# --------------------------------------------------------------------------
assessment_queries = [
    # A1
    "What is the JIRA issue number for interface 9469?",
    # A2
    "What integration style is used for interface 9469?",
    # A3
    "What is the sender system name for interface 9469?",
    # A4
    "What protocol does the sender use to send data in interface 9469?",
    # A5
    "What is the LeanIX ID for the sender system in interface 9469?",
    # A6
    "What is the receiver system name for interface 9469?",
    # A7
    "What protocol does the receiver system use in interface 9469?",
    # A8
    "What is the LeanIX ID for the receiver system in interface 9469?",
    # A9
    "What message format does the sender use for interface 9469?",
    # A10
    "What use case pattern is applied for interface 9469?",
]

# --------------------------------------------------------------------------
# Doc 3: 1064248810 — 04 [9469] Technical Specification, LS Central → S4 via TIBCO
# --------------------------------------------------------------------------
techspec_queries = [
    # TS1
    "What is the EAR name of the producer component for interface 9469?",
    # TS2
    "What is the Kong API DEV URL for the LS Central POS transaction endpoint in interface 9469?",
    # TS3
    "What authentication method is used for the Kong API in interface 9469?",
    # TS4
    "What is the Kubernetes namespace for the DEV environment in interface 9469?",
    # TS5
    "What is the Kubernetes namespace for the PROD environment in interface 9469?",
    # TS6
    "What input and output protocols does the lscentral-posdata-service producer use?",
    # TS7
    "What interface type is the lscentral-posdata-service classified as?",
    # TS8
    "What Kafka topic type does the S4 subscriber use after the T4MRSA-9142 change?",
    # TS9
    "What component was decommissioned as part of T4MGT-29674?",
    # TS10
    "What is the QA endpoint URL for the lscentral posdata service?",
]

# --------------------------------------------------------------------------
# Doc 4: 988748864_7865bb — 01 [9469] Interface Request (version 1)
# --------------------------------------------------------------------------
request1_queries = [
    # R1
    "Who is the interface owner for the 9469 interface request?",
    # R2
    "What product team is responsible for interface 9469?",
    # R3
    "What is the document title of the 9469 interface request?",
    # R4
    "What is the sender domain type in the 9469 interface request?",
    # R5
    "What is the milestone associated with interface 9469?",
    # R6
    "What is the integration blueprint pattern used for interface 9469?",
    # R7
    "What is the receiver message format specified in the 9469 interface request?",
    # R8
    "What is the receiver domain type in interface 9469?",
    # R9
    "What JIRA template issue is linked to the 9469 interface?",
    # R10
    "What is the integration layer for the 9469 interface request?",
]

# --------------------------------------------------------------------------
# Doc 5: 988748864_f8ca — 01 [9469] Interface Request (version 2)
# --------------------------------------------------------------------------
request2_queries = [
    # R2-1
    "What is the name of the interface owner listed in the 9469 interface request document?",
    # R2-2
    "What sender system LeanIX ID is referenced in the 9469 interface request?",
    # R2-3
    "What receiver system LeanIX ID is referenced in the 9469 interface request?",
    # R2-4
    "What is the sender protocol in the 9469 interface request?",
    # R2-5
    "What business area does the 9469 integration belong to based on the interface request?",
    # R2-6
    "What is the suggested reusability integration mentioned in the 9469 assessment?",
    # R2-7
    "What status is shown for the integration blueprint in the 9469 interface assessment?",
    # R2-8
    "What is the document version published on Aug 25 2023 for interface 9469?",
    # R2-9
    "What is the use case for the LS Central POS to SAP S/4 HANA integration?",
    # R2-10
    "What is the receiver system domain for interface 9469?",
]

all_queries = (
    functional_queries +
    assessment_queries +
    techspec_queries +
    request1_queries +
    request2_queries
)
labels = (
    [f"F{i}"   for i in range(1, 11)] +
    [f"A{i}"   for i in range(1, 11)] +
    [f"TS{i}"  for i in range(1, 11)] +
    [f"R{i}"   for i in range(1, 11)] +
    [f"R2-{i}" for i in range(1, 11)]
)

print("=" * 70)
print(f"Running {len(all_queries)} queries against Flogo RAG LLM Generate: {RAG}")
print(f"Collection: {COLLECTION}  topK={TOP_K}")
print("Pipeline: embed → hybrid search → LLM answer (RAGQueryGenerate)")
print("=" * 70)

for label, q in zip(labels, all_queries):
    body = json.dumps({
        "query":      q,
        "collection": COLLECTION,
        "topK":       TOP_K,
    }).encode()
    req = urllib.request.Request(
        RAG, data=body,
        headers={"Content-Type": "application/json", "accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            answer   = (data.get("answer") or "").strip()
            context  = (data.get("formattedContext") or "").strip()
            total    = data.get("totalFound", 0)
            duration = data.get("duration", "?")
            ans_prev = answer[:100].replace("\n", " ")
            print(f"[{label}] chunks={total} dur={duration} | {q[:50]}")
            print(f"       ans: {ans_prev}")
    except Exception as e:
        print(f"[{label}] ERROR {e}")

print(f"\nWaiting 120s for rageval LLM judge to score all {len(all_queries)} events...")
time.sleep(120)

# Pull metrics
try:
    url = f"http://localhost:9090/eval/v1/metrics?collection={COLLECTION}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        metrics = json.loads(resp.read())
    print("\n" + "=" * 70)
    print(f"RAGEVAL METRICS — {COLLECTION} (Flogo LLM-assisted, {len(all_queries)} queries)")
    print("=" * 70)
    print(json.dumps(metrics, indent=2))
except Exception as e:
    print(f"Metrics error: {e}")
