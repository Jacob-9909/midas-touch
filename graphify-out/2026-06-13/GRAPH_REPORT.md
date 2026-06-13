# Graph Report - midas-touch  (2026-06-13)

## Corpus Check
- 56 files · ~45,623 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1089 nodes · 1783 edges · 82 communities (74 shown, 8 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 261 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b74ca2b7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Persona Ingestion Pipeline|Persona Ingestion Pipeline]]
- [[_COMMUNITY_FastAPI GraphRAG Backend|FastAPI GraphRAG Backend]]
- [[_COMMUNITY_Project Scan Metadata|Project Scan Metadata]]
- [[_COMMUNITY_Document Parser|Document Parser]]
- [[_COMMUNITY_Embedding Config & Passages|Embedding Config & Passages]]
- [[_COMMUNITY_Dataset Builder & Hard Negatives|Dataset Builder & Hard Negatives]]
- [[_COMMUNITY_Scan Result Categories|Scan Result Categories]]
- [[_COMMUNITY_RAG Retrieval Concepts|RAG Retrieval Concepts]]
- [[_COMMUNITY_MidasAdviser Agent|MidasAdviser Agent]]
- [[_COMMUNITY_Hard Negative Mining|Hard Negative Mining]]
- [[_COMMUNITY_Market Data Ingestion|Market Data Ingestion]]
- [[_COMMUNITY_Dataset Builder Core|Dataset Builder Core]]
- [[_COMMUNITY_Knowledge Graph Builder|Knowledge Graph Builder]]
- [[_COMMUNITY_Query Synthesizer & API Keys|Query Synthesizer & API Keys]]
- [[_COMMUNITY_DB Migrations & ORM Models|DB Migrations & ORM Models]]
- [[_COMMUNITY_Module Group 15|Module Group 15]]
- [[_COMMUNITY_Module Group 16|Module Group 16]]
- [[_COMMUNITY_Module Group 17|Module Group 17]]
- [[_COMMUNITY_Module Group 18|Module Group 18]]
- [[_COMMUNITY_Module Group 19|Module Group 19]]
- [[_COMMUNITY_Module Group 20|Module Group 20]]
- [[_COMMUNITY_Module Group 21|Module Group 21]]
- [[_COMMUNITY_Module Group 22|Module Group 22]]
- [[_COMMUNITY_Module Group 23|Module Group 23]]
- [[_COMMUNITY_Module Group 25|Module Group 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Module Group 27|Module Group 27]]
- [[_COMMUNITY_Module Group 28|Module Group 28]]
- [[_COMMUNITY_Module Group 29|Module Group 29]]
- [[_COMMUNITY_Module Group 30|Module Group 30]]
- [[_COMMUNITY_Module Group 31|Module Group 31]]
- [[_COMMUNITY_Module Group 32|Module Group 32]]
- [[_COMMUNITY_Module Group 33|Module Group 33]]
- [[_COMMUNITY_Module Group 34|Module Group 34]]
- [[_COMMUNITY_Module Group 35|Module Group 35]]
- [[_COMMUNITY_Module Group 36|Module Group 36]]
- [[_COMMUNITY_Module Group 37|Module Group 37]]
- [[_COMMUNITY_Module Group 38|Module Group 38]]
- [[_COMMUNITY_Module Group 39|Module Group 39]]
- [[_COMMUNITY_Module Group 40|Module Group 40]]
- [[_COMMUNITY_Module Group 41|Module Group 41]]
- [[_COMMUNITY_Module Group 42|Module Group 42]]
- [[_COMMUNITY_Module Group 43|Module Group 43]]
- [[_COMMUNITY_Module Group 44|Module Group 44]]
- [[_COMMUNITY_Module Group 45|Module Group 45]]
- [[_COMMUNITY_Module Group 46|Module Group 46]]
- [[_COMMUNITY_Module Group 47|Module Group 47]]
- [[_COMMUNITY_Module Group 48|Module Group 48]]
- [[_COMMUNITY_Module Group 49|Module Group 49]]
- [[_COMMUNITY_Module Group 50|Module Group 50]]
- [[_COMMUNITY_Module Group 51|Module Group 51]]
- [[_COMMUNITY_Module Group 52|Module Group 52]]
- [[_COMMUNITY_Module Group 53|Module Group 53]]
- [[_COMMUNITY_Module Group 54|Module Group 54]]
- [[_COMMUNITY_Module Group 55|Module Group 55]]
- [[_COMMUNITY_Module Group 56|Module Group 56]]
- [[_COMMUNITY_Module Group 57|Module Group 57]]
- [[_COMMUNITY_Module Group 58|Module Group 58]]
- [[_COMMUNITY_Module Group 59|Module Group 59]]
- [[_COMMUNITY_Module Group 60|Module Group 60]]
- [[_COMMUNITY_Module Group 61|Module Group 61]]
- [[_COMMUNITY_Module Group 62|Module Group 62]]
- [[_COMMUNITY_Module Group 63|Module Group 63]]
- [[_COMMUNITY_Module Group 64|Module Group 64]]
- [[_COMMUNITY_Module Group 65|Module Group 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Module Group 69|Module Group 69]]
- [[_COMMUNITY_Module Group 70|Module Group 70]]
- [[_COMMUNITY_Module Group 71|Module Group 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Module Group 77|Module Group 77]]
- [[_COMMUNITY_Module Group 79|Module Group 79]]
- [[_COMMUNITY_Module Group 80|Module Group 80]]
- [[_COMMUNITY_Module Group 81|Module Group 81]]
- [[_COMMUNITY_Module Group 82|Module Group 82]]
- [[_COMMUNITY_Community 83|Community 83]]

## God Nodes (most connected - your core abstractions)
1. `PipelineConfig` - 63 edges
2. `SyntheticQuery` - 39 edges
3. `files` - 37 edges
4. `importMap` - 37 edges
5. `APIKeyRotator` - 37 edges
6. `Passage` - 36 edges
7. `EmbeddingDatasetPipeline` - 34 edges
8. `db_cursor()` - 30 edges
9. `PathConfig` - 28 edges
10. `QuerySynthesizer` - 28 edges

## Surprising Connections (you probably didn't know these)
- `TestDatabaseHelpers` --uses--> `ChatRequest`  [INFERRED]
  tests/test_agent.py → backend/app/api/chat.py
- `main()` --calls--> `SentenceTransformer`  [INFERRED]
  pipelines/data_ingestion/ingest_personas.py → backend/app/services/agent/tools/_embedding.py
- `QuerySynthesisConfig` --uses--> `APIKeyRotator`  [INFERRED]
  pipelines/embedding/config.py → shared/utils/api_key_rotator.py
- `PathConfig` --uses--> `APIKeyRotator`  [INFERRED]
  pipelines/embedding/config.py → shared/utils/api_key_rotator.py
- `SentenceTransformer` --uses--> `PathConfig`  [INFERRED]
  backend/app/services/agent/tools/_embedding.py → pipelines/embedding/config.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Embedding dataset generation pipeline: DocumentParser -> QuerySynthesizer -> HardNegativeMiner -> TripletAssembler** — embedding_documentparser_documentparser, embedding_querysynthesizer_querysynthesizer, embedding_hardnegativeminer_hardnegativeminer, embedding_datasetbuilder_tripletassembler, embedding_pipeline_embeddingdatasetpipeline [EXTRACTED 1.00]
- **Investor persona generation and embedding ingestion: export_csv -> generate_finance_data -> ingest_personas** — data_ingestion_exportcsv_script, data_ingestion_generatefinance_generatefinancedata, data_ingestion_ingestpersonas_main, concept_persona_embeddings [INFERRED 0.95]
- **RAG-based financial advisory: persona embeddings + market snapshots + tax rules -> MidasAdviser -> recommendation report** — concept_persona_embeddings, concept_market_snapshots, agent_recommender_midasadviser, agent_recommender_getrecommendation, concept_twin_persona_rag [EXTRACTED 1.00]
- **GraphRAG Pipeline: Builder + EntityRefiner + TestRAG share Neo4j store and BAAI/bge-m3 embedding** — knowledge_graph_builder_buildknowledgegraph, knowledge_graph_entity_resolution_entityrefiner, knowledge_graph_test_rag_rungraphragquery, concept_neo4j_propertygraph, concept_baai_bgem3 [INFERRED 0.95]
- **PostgreSQL schema defined consistently across ORM models, SQL schema, and Alembic migrations** — models_postgres_models_user, schema_postgres_schema_sql, migrations_env_runmigrations, migrations_a1b2c3d4_addembeddingtables, migrations_d93ff1c5_consolidatedinitial [INFERRED 0.90]
- **NIMOpenAI rate limit handling: APIKeyRotator + dynamic backoff form a unified retry/rotation pattern** — utils_nim_openai_nimopenai, utils_api_key_rotator_apikeyrotator, utils_nim_openai_ratelimit_pattern, concept_nvidia_nim [EXTRACTED 0.95]

## Communities (82 total, 8 thin omitted)

### Community 0 - "Persona Ingestion Pipeline"
Cohesion: 0.10
Nodes (34): LoRA Fine-tuning for embedding model (PEFT), Dataset, compute_dataset_stats(), DatasetIO, 쿼리 타입 분포를 유지하며 학습/평가셋 분리., Triplet 리스트 ↔ JSONL 파일 입출력., Triplet 리스트를 JSONL 파일로 저장., JSONL 파일에서 Triplet 리스트 로드. (+26 more)

### Community 1 - "FastAPI GraphRAG Backend"
Cohesion: 0.13
Nodes (15): Exception, main(), test_rag.py ----------- LlamaIndex + Neo4j 기반 지식 그래프 RAG (GraphRAG) 질의 추론 테스트 실행, LlamaIndex의 전역 LLM 및 임베딩 모델 설정., 구축된 Neo4j 지식 그래프를 대상으로 다중 홉(Multi-hop) GraphRAG 질의 추론 실행., run_graph_rag_query(), setup_llamaindex_settings(), LLMMetadata (+7 more)

### Community 2 - "Project Scan Metadata"
Cohesion: 0.05
Nodes (37): importMap, alembic.ini, database/migrations/postgres/env.py, database/migrations/postgres/README, database/migrations/postgres/script.py.mako, database/migrations/postgres/versions/a1b2c3d4e5f6_add_embedding_pipeline_tables.py, database/migrations/postgres/versions/d93ff1c5811e_consolidated_initial_schema.py, database/schema/postgres_schema.sql (+29 more)

### Community 3 - "Document Parser"
Cohesion: 0.07
Nodes (27): Gemini Vision OCR Fallback for corrupted/scanned PDFs, DocumentParser, FinancialChunker, 재귀적으로 구분자를 활용해 분할한 후 적절한 오버랩을 주어 그룹화., 다양한 형식(PDF, TXT, MD)의 금융 문서를 자동으로 파싱하고     고품질 임베딩 단락(Passage)으로 정제 청킹하는 리더., 단일 파일 경로를 읽어 확장자에 알맞게 파싱 및 청킹 수행.          Returns:             Passage 인스턴스 목록, pymupdf를 기본으로 사용하고 pypdf를 보완적으로 사용하여 텍스트 및 표 데이터를 고품질로 추출., 텍스트 레이어 손상 감지: 공백으로 분리된 토큰 대부분이 1글자면 깨진 것으로 판단.          정상 한글 본문은 '주택임대소득' 같은 다 (+19 more)

### Community 4 - "Embedding Config & Passages"
Cohesion: 0.16
Nodes (15): pgvector HNSW Vector Search, bulk_upsert_emb_passages, bulk_upsert_users, db_cursor, get_all_tax_rules, get_connection, search_similar_personas_db, upsert_market_snapshot (+7 more)

### Community 5 - "Dataset Builder & Hard Negatives"
Cohesion: 0.13
Nodes (19): DatasetSplitter, 삼중쌍을 학습/평가셋으로 분리 (쿼리 단위 stratified split)., DatasetSplitter, HardNegativeCandidate, CheckpointManager, EmbeddingDatasetPipeline, main(), PassageLoader (+11 more)

### Community 6 - "Scan Result Categories"
Cohesion: 0.07
Nodes (28): code, config, data, docs, infra, script, config, ipynb (+20 more)

### Community 7 - "RAG Retrieval Concepts"
Cohesion: 0.12
Nodes (18): KURE-v1 (nlpai-lab Korean embedding model, 1024-dim), NVIDIA NIM API (LLM inference endpoint), NV-Retriever Margin Hard Negative Filtering, Persona Embeddings (pgvector table for investor persona semantic search), RRF Hybrid Retrieval (Dense + BM25 Sparse fusion), export_csv (Nemotron-Personas-Korea export), generate_finance_data (async LLM persona generator), ingest_personas main (KURE-v1 embedding + pgvector upsert) (+10 more)

### Community 8 - "MidasAdviser Agent"
Cohesion: 0.17
Nodes (13): SentenceTransformer, embed(), get_embedding_model(), get_llamaindex_embedding(), 프로젝트 통합 임베딩(BAAI/bge-m3) 싱글톤.  이 모듈은 백엔드 에이전트의 모든 검색 도구가 공유하는 **단일** 임베딩 진입점이다., 프로세스 전역에서 한 번만 로드되는 bge-m3 모델 인스턴스를 반환한다., 단일 텍스트를 1024차원 bge-m3 벡터로 인코딩한다 (persona_embeddings 적재와 동일 방식)., 위 단일 SentenceTransformer를 감싸는 LlamaIndex BaseEmbedding 어댑터(캐시).      graph_rag가 (+5 more)

### Community 9 - "Hard Negative Mining"
Cohesion: 0.09
Nodes (20): HardNegativeMiner, sentence-transformers 기반 교사 임베딩 모델 래퍼.     배치 처리 + 정규화 + GPU/CPU 자동 선택., 텍스트 리스트를 배치 임베딩으로 변환., 교사 임베딩 모델 + BM25 sparse index + NV-Retriever 마진 필터를 결합한 RRF 하이브리드 하드 네거티브 마이닝., 전체 단락 코퍼스를 임베딩하고 BM25 Sparse 인덱스도 구축., 쿼리 리스트 전체에 대해 RRF 하이브리드 하드 네거티브 마이닝 수행., Dense 스코어와 Sparse 스코어의 순위를 매겨 RRF 점수를 계산합니다., RRF 순위가 높은 후보 위주로 탐색하되, NV-Retriever 마진 규격은 Dense 코사인 유사도로 검사. (+12 more)

### Community 10 - "Market Data Ingestion"
Cohesion: 0.15
Nodes (13): fetch_ecos_data(), fetch_fred_data(), fetch_realtime_stock(), fetch_yfinance_data(), main(), MarketDataPipeline, Market Data Fetcher from open APIs (yfinance, FRED, ECOS).  This module manages, Fetch history from BOK ECOS API. (+5 more)

### Community 11 - "Dataset Builder Core"
Cohesion: 0.14
Nodes (22): PipelineConfig, dataset_builder.py ------------------ (Query, Positive, Negative) 삼중쌍 조립 및 데이터셋, 긍정 단락을 제외하고 랜덤 단락 샘플링., SyntheticQuery + MiningResult를 결합하여 Triplet 리스트 생성., TripletAssembler, compute_mining_stats(), MiningResult, NVRetrieverMarginFilter (+14 more)

### Community 12 - "Knowledge Graph Builder"
Cohesion: 0.12
Nodes (19): Document, get_processed_passage_ids(), get_processed_passage_ids, init_checkpoint_table(), init_checkpoint_table, load_passages_as_documents(), load_passages_as_documents, main() (+11 more)

### Community 13 - "Query Synthesizer & API Keys"
Cohesion: 0.06
Nodes (28): HardNegativeConfig, LoraConfig, NIMConfig, PromptTemplates, QuerySynthesisConfig, config.py --------- 금융 특화 임베딩 파인튜닝 파이프라인의 모든 설정값·프롬프트·스키마를 코드와 분리 관리. 환경변수(.env), KURE-v1 파인튜닝 하이퍼파라미터., NVIDIA NIM API 접속 설정. (+20 more)

### Community 14 - "DB Migrations & ORM Models"
Cohesion: 0.29
Nodes (14): migrations.env.run_migrations_online, SQLAlchemy Models package for consolidated Midas Touch database schemas., LegalReference, MacroIndicator, MarketSnapshot, NewsEmbedding, PersonaEmbedding, Portfolio (+6 more)

### Community 15 - "Module Group 15"
Cohesion: 0.19
Nodes (11): get_all_tax_rules(), get_latest_market_snapshots(), Retrieve all current active tax rules., Retrieve the latest snapshot value for every unique (data_type, sub_key) pair., Midas Touch 백엔드 에이전트 & DB 헬퍼 통합 테스트.  실행:     PYTHONPATH=. uv run python -m unit, shared.database.connector 조회 헬퍼 검증., shared.database.connector 조회 헬퍼 검증., TestDatabaseHelpers (+3 more)

### Community 16 - "Module Group 16"
Cohesion: 0.17
Nodes (19): apply_schema(), bulk_upsert_emb_passages(), bulk_upsert_emb_queries(), bulk_upsert_emb_triplets(), bulk_upsert_market_snapshots(), db_cursor(), get_latest_market_value(), Consolidated PostgreSQL & pgvector Database connector for Midas Touch. (+11 more)

### Community 17 - "Module Group 17"
Cohesion: 0.12
Nodes (20): Passage, 정제 및 청킹이 완료된 개별 금융 문서 단락., _classify_query_type(), QuerySynthesizer, query_synthesizer.py -------------------- NVIDIA NIM API를 활용한 비동기 금융 쿼리 합성 및 2차, 단락 리스트를 받아 LLM 기반 쿼리를 비동기 대량 합성 + 2차 품질 검증., 단락 리스트 전체에 대해 비동기 병렬 쿼리 합성 및 검증., 단락 리스트 전체에 대해 비동기 병렬 쿼리 합성을 진행하면서,          완료될 때마다 실시간으로 체크포인트 파일에 추가 저장하고 진행률을 (+12 more)

### Community 18 - "Module Group 18"
Cohesion: 0.19
Nodes (11): EntityRefiner, main(), entity_resolution.py -------------------- Neo4j 지식 그래프의 동적 엔티티 중복 정제(Entity Reso, Neo4j DB에서 모든 Entity 노드 정보(이름, 라벨)를 조회., LLM을 호출하여 두 노드의 금융/세무적 의미가 완벽히 동일한지 판별., Python-driven 관계 이전 및 구 노드 DETACH DELETE 안전 병합 트랜잭션 수행., 지정한 시간 주기마다 백그라운드에서 엔티티 정제를 무한히 자동 가동하는 데몬 루프., 지식 그래프의 중복 엔티티를 정밀 진단 및 병합 정제하는 클래스. (+3 more)

### Community 19 - "Module Group 19"
Cohesion: 0.12
Nodes (15): 1. 데이터베이스 마이그레이션 최신화, 2. FastAPI 실시간 웹 서버 실행, 3. 멀티턴 금융 에이전트 (LangGraph) 호출, 4. 거시경제 지표 수집 배치 가동 (yfinance API 연동), 5. 유저 페르소나 데이터셋 빌드 및 DB 적재, 6. 금융 임베딩 학습 전처리 파이프라인 실행, 7. 지식 그래프 구축 및 RAG 질의 테스트, 8. 손상 PDF 문서 강제 재파싱 복구 (+7 more)

### Community 20 - "Module Group 20"
Cohesion: 0.27
Nodes (11): get_client(), Consolidated supabase_connector routing vector operations directly to the unifie, Mock get_client for backward compatibility., search_news(), search_similar_personas(), search_strategies(), upsert_macro_indicator(), upsert_news() (+3 more)

### Community 21 - "Module Group 21"
Cohesion: 0.15
Nodes (12): edges, layers, nodes, project, analyzedAt, description, frameworks, gitCommitHash (+4 more)

### Community 22 - "Module Group 22"
Cohesion: 0.40
Nodes (5): Market Snapshots (macroeconomic indicators: exchange rates, interest rates, commodities, indices), fetch_ecos_data, fetch_fred_data, fetch_yfinance_data, MarketDataPipeline

### Community 23 - "Module Group 23"
Cohesion: 0.05
Nodes (40): get_checkpointer(), LangGraph 체크포인터 (PostgresSaver) 구성.  멀티턴 대화 상태를 Postgres에 영속화한다 — MemorySaver와 달, 앱 수명 동안 유지되는 PostgresSaver(커넥션 풀 기반)를 1회 생성해 캐시한다., build_agent(), get_agent(), intent 분기 StateGraph를 구성해 컴파일한다., 컴파일된 그래프(CompiledStateGraph)를 1회 생성 후 캐시한다.      체크포인터는 PostgresSaver(영속·다중워커 공유, intent 분기 StateGraph를 구성해 컴파일한다. (+32 more)

### Community 26 - "Community 26"
Cohesion: 0.19
Nodes (12): Any, Any, get_user_by_uuid(), Search similar personas in our PostgreSQL database using the custom pgvector sea, search_similar_personas_db(), pgvector 유사도 검색 + Users 프로필 조인 (1024차원 bge-m3 공간)., pgvector 유사도 검색 + Users 프로필 조인 (1024차원 bge-m3 공간)., _format_rag_context() (+4 more)

### Community 27 - "Module Group 27"
Cohesion: 0.06
Nodes (49): _classify_intent(), _dispatch(), _keyword_route(), _latest_user_text(), _node_graph_rag(), _node_persona_rag(), _node_synthesize(), _node_tax_lookup() (+41 more)

### Community 29 - "Module Group 29"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 30 - "Module Group 30"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 31 - "Module Group 31"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 32 - "Module Group 32"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 33 - "Module Group 33"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 34 - "Module Group 34"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 35 - "Module Group 35"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 36 - "Module Group 36"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 37 - "Module Group 37"
Cohesion: 0.22
Nodes (9): classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports, totalLines (+1 more)

### Community 38 - "Module Group 38"
Cohesion: 0.22
Nodes (9): notebooks/exploration.ipynb, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 39 - "Module Group 39"
Cohesion: 0.22
Nodes (9): pyproject.toml, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 40 - "Module Group 40"
Cohesion: 0.22
Nodes (9): README.md, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 41 - "Module Group 41"
Cohesion: 0.22
Nodes (9): scripts/db_init.sh, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 42 - "Module Group 42"
Cohesion: 0.22
Nodes (9): scripts/migrate_data.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 43 - "Module Group 43"
Cohesion: 0.22
Nodes (9): scripts/oracle_macro.sh, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 44 - "Module Group 44"
Cohesion: 0.22
Nodes (9): scripts/run_agent.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 45 - "Module Group 45"
Cohesion: 0.22
Nodes (9): scripts/run_market_pipeline.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 46 - "Module Group 46"
Cohesion: 0.22
Nodes (9): scripts/run_persona_pipeline.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 47 - "Module Group 47"
Cohesion: 0.22
Nodes (9): src/agent/recommender.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 48 - "Module Group 48"
Cohesion: 0.22
Nodes (9): src/data_pipeline/export_csv.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 49 - "Module Group 49"
Cohesion: 0.22
Nodes (9): src/data_pipeline/fetch_market_data.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 50 - "Module Group 50"
Cohesion: 0.22
Nodes (9): src/data_pipeline/generate_finance_data.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 51 - "Module Group 51"
Cohesion: 0.22
Nodes (9): src/db/connector.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 52 - "Module Group 52"
Cohesion: 0.22
Nodes (9): src/db/models/__init__.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 53 - "Module Group 53"
Cohesion: 0.22
Nodes (9): src/db/models/postgres_models.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 54 - "Module Group 54"
Cohesion: 0.22
Nodes (9): src/db/supabase_connector.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 55 - "Module Group 55"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/config.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 56 - "Module Group 56"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/dataset_builder.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 57 - "Module Group 57"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/document_parser.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 58 - "Module Group 58"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/hard_negative_miner.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 59 - "Module Group 59"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/__init__.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 60 - "Module Group 60"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/pipeline.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 61 - "Module Group 61"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/query_synthesizer.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 62 - "Module Group 62"
Cohesion: 0.22
Nodes (9): src/embedding_pipeline/train.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 63 - "Module Group 63"
Cohesion: 0.22
Nodes (9): tests/test_agent.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 64 - "Module Group 64"
Cohesion: 0.22
Nodes (9): tests/test_document_parser.py, classes, contentHash, exports, filePath, functions, hasStructuralAnalysis, imports (+1 more)

### Community 66 - "Community 66"
Cohesion: 0.20
Nodes (8): GoogleGenAI, build_knowledge_graph(), Save the successfully processed passage IDs to PostgreSQL., Neo4j 데이터베이스에 세법 및 금융 자산 지식 그래프 자동 구축., Save the successfully processed passage IDs to PostgreSQL., Neo4j 데이터베이스에 세법 및 금융 자산 지식 그래프 자동 구축., save_processed_passage_ids(), Neo4j, 임베딩, LLM 등 필요한 외부 커넥션 초기화.

### Community 67 - "Community 67"
Cohesion: 0.28
Nodes (9): BAAI/bge-m3 Korean Embedding Model, Embedding-based Entity Resolution, Google Gemini via Vertex AI, NVIDIA NIM OpenAI-compatible API, setup_llamaindex_settings, EntityRefiner._merge_nodes_neo4j, EntityRefiner.run_resolution, EntityRefiner._verify_duplicate_with_llm (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.25
Nodes (6): Neo4j PropertyGraph Store, build_knowledge_graph, Incremental Graph Build Checkpoint Pattern, save_processed_passage_ids, Multi-hop GraphRAG Query Pattern, run_graph_rag_query

### Community 69 - "Module Group 69"
Cohesion: 0.47
Nodes (5): get_database_url(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 70 - "Module Group 70"
Cohesion: 0.40
Nodes (4): files, generatedAt, gitCommitHash, version

### Community 71 - "Module Group 71"
Cohesion: 0.40
Nodes (4): analyzedFiles, gitCommitHash, lastAnalyzedAt, version

### Community 72 - "Community 72"
Cohesion: 0.32
Nodes (7): extract_json(), generate_finance_data(), main(), 개별 행에 대해 LLM을 호출하여 금융 데이터를 생성합니다., LLM 출력에서 JSON 부분만 추출하는 헬퍼 함수, bulk_upsert_users(), Batch upsert. Returns count of rows processed.

### Community 83 - "Community 83"
Cohesion: 0.67
Nodes (3): bootstrap_supabase_schema(), main(), Midas Touch Persona Ingestion and Vector Embedding Pipeline.  This script: 1. Bo

## Knowledge Gaps
- **430 isolated node(s):** `version`, `gitCommitHash`, `generatedAt`, `filePath`, `contentHash` (+425 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `files` connect `Module Group 70` to `Module Group 29`, `Module Group 30`, `Module Group 31`, `Module Group 32`, `Module Group 33`, `Module Group 34`, `Module Group 35`, `Module Group 36`, `Module Group 37`, `Module Group 38`, `Module Group 39`, `Module Group 40`, `Module Group 41`, `Module Group 42`, `Module Group 43`, `Module Group 44`, `Module Group 45`, `Module Group 46`, `Module Group 47`, `Module Group 48`, `Module Group 49`, `Module Group 50`, `Module Group 51`, `Module Group 52`, `Module Group 53`, `Module Group 54`, `Module Group 55`, `Module Group 56`, `Module Group 57`, `Module Group 58`, `Module Group 59`, `Module Group 60`, `Module Group 61`, `Module Group 62`, `Module Group 63`, `Module Group 64`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `NIMOpenAI` connect `FastAPI GraphRAG Backend` to `MidasAdviser Agent`, `Community 67`, `Query Synthesizer & API Keys`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `db_cursor()` connect `Module Group 16` to `Persona Ingestion Pipeline`, `Community 66`, `Community 72`, `Knowledge Graph Builder`, `Module Group 15`, `Module Group 20`, `Module Group 23`, `Community 26`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 49 inferred relationships involving `PipelineConfig` (e.g. with `Dataset` and `APIKeyRotator`) actually correct?**
  _`PipelineConfig` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `SyntheticQuery` (e.g. with `DatasetIO` and `DatasetSplitter`) actually correct?**
  _`SyntheticQuery` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `APIKeyRotator` (e.g. with `HardNegativeConfig` and `LoraConfig`) actually correct?**
  _`APIKeyRotator` has 21 INFERRED edges - model-reasoned connections that need verification._
- **What connects `version`, `gitCommitHash`, `generatedAt` to the rest of the system?**
  _627 weakly-connected nodes found - possible documentation gaps or missing edges._