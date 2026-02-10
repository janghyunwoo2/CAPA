# Global Development Persona Structure

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  📋 Global Development Persona Architecture                                  ║
║  버전: 1.0.0 | 최종 수정: 2026-02-01                                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  목적: LLM 에이전트 구조를 일반화한 글로벌 개발 페르소나 폴더 구성            ║
║  적용: Backend, Frontend, Data, DevOps, ML 등 모든 개발 도메인               ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 1. 아키텍처 개요

### 1.1 계층 구조 (5-Layer Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Global Development Persona Layers                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Layer 5] CONTEXT       실행 환경, 메모리, 세션 관리                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Layer 4] KNOWLEDGE     도메인 지식, 템플릿, 패턴                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Layer 3] TOOLS         실행 도구, 어댑터, 레지스트리                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Layer 2] WORKFLOW      실행 흐름, 오케스트레이션, 상태 관리         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  [Layer 1] AGENTS        전문가 정의, 역할, 프롬프트                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 계층별 역할

| Layer | 이름 | 역할 | 질문 | LLM 대응 |
|-------|------|------|------|----------|
| 1 | **AGENTS** | 전문가 정의 | WHO (누가) | agents/ |
| 2 | **WORKFLOW** | 실행 흐름 | HOW (어떻게) | workflow/ |
| 3 | **TOOLS** | 도구/장비 | WITH (무엇으로) | tools/ |
| 4 | **KNOWLEDGE** | 도메인 지식 | WHAT (무엇을) | - (신규) |
| 5 | **CONTEXT** | 실행 환경 | WHERE (어디서) | - (신규) |

---

## 2. 폴더 구조

### 2.1 전체 구조

```
personas/
│
├── [DOMAIN]/                           # 도메인별 페르소나
│   │                                   # (backend, frontend, data, devops, ml)
│   │
│   ├── agents/                         # ═══ [Layer 1] 전략 계층 ═══
│   │   │                               # 전문가 정의 (WHO)
│   │   │
│   │   ├── core/                       # 핵심 에이전트
│   │   │   ├── agent.py               # 에이전트 클래스 정의
│   │   │   ├── prompts.py             # 프롬프트/지시문 템플릿
│   │   │   └── config.yaml            # 설정 (모델, 파라미터)
│   │   │
│   │   ├── specialist/                 # 전문 분야 에이전트
│   │   │   ├── architect/             # 아키텍트 에이전트
│   │   │   │   ├── agent.py
│   │   │   │   └── prompts.py
│   │   │   ├── reviewer/              # 코드 리뷰어 에이전트
│   │   │   │   ├── agent.py
│   │   │   │   └── prompts.py
│   │   │   ├── debugger/              # 디버거 에이전트
│   │   │   │   ├── agent.py
│   │   │   │   └── prompts.py
│   │   │   └── optimizer/             # 최적화 에이전트
│   │   │       ├── agent.py
│   │   │       └── prompts.py
│   │   │
│   │   └── intent/                     # 의도 분석기 (Router Brain)
│   │       ├── analyzer.py            # 의도 분석 로직
│   │       ├── prompts.py             # 분석용 프롬프트
│   │       └── rules.yaml             # 라우팅 규칙 정의
│   │
│   ├── workflow/                       # ═══ [Layer 2] 실행 계층 ═══
│   │   │                               # 워크플로우 정의 (HOW)
│   │   │
│   │   ├── main/                      # (Level 1) 메인 오케스트레이터
│   │   │   ├── orchestrator.py        # 메인 그래프/플로우 정의
│   │   │   ├── state.py               # 글로벌 상태 관리 (AgentState)
│   │   │   └── transitions.yaml       # 상태 전이 규칙
│   │   │
│   │   └── sub/                       # (Level 2) 서브 워크플로우
│   │       ├── review/                # 코드 리뷰 워크플로우
│   │       │   ├── workflow.py        # Sub-graph (Think-Act Loop)
│   │       │   ├── state.py           # ReviewState
│   │       │   └── steps.yaml         # 단계 정의
│   │       ├── build/                 # 빌드 워크플로우
│   │       │   ├── workflow.py
│   │       │   ├── state.py
│   │       │   └── steps.yaml
│   │       ├── deploy/                # 배포 워크플로우
│   │       │   ├── workflow.py
│   │       │   ├── state.py
│   │       │   └── steps.yaml
│   │       └── debug/                 # 디버깅 워크플로우
│   │           ├── workflow.py
│   │           ├── state.py
│   │           └── steps.yaml
│   │
│   ├── tools/                          # ═══ [Layer 3] 도구 계층 ═══
│   │   │                               # 실행 도구 (WITH)
│   │   │
│   │   ├── factory.py                 # ToolManager (도구 주입기)
│   │   ├── registry.py                # 도구 레지스트리
│   │   │
│   │   └── adapters/                  # 외부 도구 어댑터
│   │       ├── cli.py                 # CLI 도구 래퍼 (git, npm, docker)
│   │       ├── api.py                 # API 클라이언트 (REST, GraphQL)
│   │       ├── file.py                # 파일 시스템 도구
│   │       ├── database.py            # DB 도구 (SQL, NoSQL)
│   │       └── cloud.py               # 클라우드 도구 (AWS, GCP, Azure)
│   │
│   ├── knowledge/                      # ═══ [Layer 4] 지식 계층 ═══
│   │   │                               # 도메인 지식 (WHAT)
│   │   │
│   │   ├── docs/                      # 참조 문서
│   │   │   ├── architecture.md        # 아키텍처 문서
│   │   │   ├── standards.md           # 코딩 표준
│   │   │   └── glossary.md            # 용어 정의
│   │   │
│   │   ├── templates/                 # 코드/문서 템플릿
│   │   │   ├── code/                  # 코드 템플릿
│   │   │   ├── config/                # 설정 파일 템플릿
│   │   │   └── docs/                  # 문서 템플릿
│   │   │
│   │   └── patterns/                  # 설계 패턴/베스트 프랙티스
│   │       ├── design_patterns.md     # 디자인 패턴
│   │       ├── anti_patterns.md       # 안티 패턴
│   │       └── best_practices.md      # 베스트 프랙티스
│   │
│   └── context/                        # ═══ [Layer 5] 컨텍스트 계층 ═══
│       │                               # 실행 환경 (WHERE)
│       │
│       ├── memory.py                  # 대화/작업 메모리
│       ├── session.py                 # 세션 관리
│       ├── history.py                 # 작업 히스토리
│       └── cache.py                   # 캐시 관리
│
├── shared/                             # ═══ 공유 컴포넌트 ═══
│   │
│   ├── base/                          # 베이스 클래스
│   │   ├── agent_base.py              # AgentBase 추상 클래스
│   │   ├── workflow_base.py           # WorkflowBase 추상 클래스
│   │   ├── tool_base.py               # ToolBase 추상 클래스
│   │   └── state_base.py              # StateBase 추상 클래스
│   │
│   ├── utils/                         # 공통 유틸리티
│   │   ├── logger.py                  # 로깅 유틸리티
│   │   ├── validator.py               # 검증 유틸리티
│   │   └── formatter.py               # 포맷팅 유틸리티
│   │
│   └── interfaces/                    # 인터페이스 정의
│       ├── i_agent.py                 # IAgent 인터페이스
│       ├── i_workflow.py              # IWorkflow 인터페이스
│       └── i_tool.py                  # ITool 인터페이스
│
└── config/                             # ═══ 글로벌 설정 ═══
    │
    ├── personas.yaml                  # 페르소나 매핑 정의
    ├── routing.yaml                   # 도메인 라우팅 규칙
    ├── capabilities.yaml              # 역량 매트릭스
    └── environments.yaml              # 환경별 설정
```

---

## 3. 도메인별 페르소나 예시

### 3.1 Backend 페르소나

```
personas/backend/
├── agents/
│   ├── core/                          # 백엔드 핵심 에이전트
│   ├── specialist/
│   │   ├── api_designer/              # API 설계 전문가
│   │   ├── db_architect/              # DB 아키텍트
│   │   ├── security_auditor/          # 보안 감사
│   │   └── performance_tuner/         # 성능 최적화
│   └── intent/
├── workflow/
│   └── sub/
│       ├── api_design/                # API 설계 플로우
│       ├── db_migration/              # DB 마이그레이션 플로우
│       └── security_check/            # 보안 검사 플로우
├── tools/
│   └── adapters/
│       ├── orm.py                     # ORM 도구 (SQLAlchemy, Prisma)
│       ├── rest.py                    # REST API 도구
│       └── queue.py                   # 메시지 큐 도구
└── knowledge/
    ├── docs/
    │   └── api_standards.md           # API 표준
    └── patterns/
        └── backend_patterns.md        # 백엔드 패턴
```

### 3.2 Frontend 페르소나

```
personas/frontend/
├── agents/
│   ├── core/
│   ├── specialist/
│   │   ├── ui_designer/               # UI 설계 전문가
│   │   ├── ux_analyst/                # UX 분석가
│   │   ├── accessibility_expert/      # 접근성 전문가
│   │   └── performance_optimizer/     # 성능 최적화
│   └── intent/
├── workflow/
│   └── sub/
│       ├── component_design/          # 컴포넌트 설계
│       ├── state_management/          # 상태 관리
│       └── responsive_design/         # 반응형 설계
├── tools/
│   └── adapters/
│       ├── bundler.py                 # 번들러 (Webpack, Vite)
│       ├── testing.py                 # 테스트 도구 (Jest, Cypress)
│       └── linter.py                  # 린터 (ESLint, Prettier)
└── knowledge/
    └── patterns/
        └── component_patterns.md      # 컴포넌트 패턴
```

### 3.3 Data 페르소나

```
personas/data/
├── agents/
│   ├── core/
│   ├── specialist/
│   │   ├── etl_engineer/              # ETL 엔지니어
│   │   ├── data_modeler/              # 데이터 모델러
│   │   ├── quality_analyst/           # 품질 분석가
│   │   └── pipeline_architect/        # 파이프라인 아키텍트
│   └── intent/
├── workflow/
│   └── sub/
│       ├── etl_pipeline/              # ETL 파이프라인
│       ├── data_validation/           # 데이터 검증
│       └── lakehouse_design/          # 레이크하우스 설계
├── tools/
│   └── adapters/
│       ├── spark.py                   # Spark 도구
│       ├── airflow.py                 # Airflow 도구
│       └── dbt.py                     # dbt 도구
└── knowledge/
    └── patterns/
        └── medallion_architecture.md  # 메달리온 아키텍처
```

### 3.4 DevOps 페르소나

```
personas/devops/
├── agents/
│   ├── core/
│   ├── specialist/
│   │   ├── ci_cd_engineer/            # CI/CD 엔지니어
│   │   ├── infra_architect/           # 인프라 아키텍트
│   │   ├── sre_engineer/              # SRE 엔지니어
│   │   └── security_ops/              # 보안 운영
│   └── intent/
├── workflow/
│   └── sub/
│       ├── deployment/                # 배포 플로우
│       ├── monitoring_setup/          # 모니터링 설정
│       └── incident_response/         # 인시던트 대응
├── tools/
│   └── adapters/
│       ├── docker.py                  # Docker 도구
│       ├── kubernetes.py              # Kubernetes 도구
│       ├── terraform.py               # Terraform 도구
│       └── ansible.py                 # Ansible 도구
└── knowledge/
    └── patterns/
        └── gitops_patterns.md         # GitOps 패턴
```

---

## 4. 핵심 컴포넌트 상세

### 4.1 Agent 정의 (agents/core/agent.py)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class AgentConfig:
    """에이전트 설정"""
    name: str
    role: str
    capabilities: List[str]
    tools: List[str]
    model: str = "default"
    temperature: float = 0.7

class BaseAgent(ABC):
    """에이전트 베이스 클래스"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.tools = []
        self.memory = []

    @abstractmethod
    def think(self, input: str) -> str:
        """사고 로직"""
        pass

    @abstractmethod
    def act(self, thought: str) -> Any:
        """실행 로직"""
        pass

    def process(self, input: str) -> Any:
        """Think-Act Loop"""
        thought = self.think(input)
        result = self.act(thought)
        self.memory.append({"input": input, "thought": thought, "result": result})
        return result
```

### 4.2 Workflow 정의 (workflow/main/orchestrator.py)

```python
from typing import Dict, Any, Callable
from enum import Enum, auto

class WorkflowState(Enum):
    """워크플로우 상태"""
    INIT = auto()
    ANALYZING = auto()
    ROUTING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()

class MainOrchestrator:
    """메인 오케스트레이터"""

    def __init__(self):
        self.state = WorkflowState.INIT
        self.agents: Dict[str, Any] = {}
        self.sub_workflows: Dict[str, Callable] = {}
        self.intent_analyzer = None

    def register_agent(self, name: str, agent: Any):
        """에이전트 등록"""
        self.agents[name] = agent

    def register_workflow(self, name: str, workflow: Callable):
        """서브 워크플로우 등록"""
        self.sub_workflows[name] = workflow

    def analyze_intent(self, input: str) -> str:
        """의도 분석"""
        self.state = WorkflowState.ANALYZING
        return self.intent_analyzer.analyze(input)

    def route(self, intent: str) -> str:
        """라우팅"""
        self.state = WorkflowState.ROUTING
        # 의도에 따른 적절한 서브 워크플로우 선택
        return self._select_workflow(intent)

    def execute(self, workflow_name: str, context: Dict) -> Any:
        """실행"""
        self.state = WorkflowState.EXECUTING
        workflow = self.sub_workflows.get(workflow_name)
        if workflow:
            return workflow(context)
        raise ValueError(f"Unknown workflow: {workflow_name}")

    def run(self, input: str) -> Any:
        """메인 실행 루프"""
        try:
            intent = self.analyze_intent(input)
            workflow_name = self.route(intent)
            result = self.execute(workflow_name, {"input": input, "intent": intent})
            self.state = WorkflowState.COMPLETED
            return result
        except Exception as e:
            self.state = WorkflowState.FAILED
            raise e
```

### 4.3 Tool Factory (tools/factory.py)

```python
from typing import Dict, List, Type, Any

class ToolRegistry:
    """도구 레지스트리"""

    _tools: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, tool_class: Type):
        """도구 등록"""
        cls._tools[name] = tool_class

    @classmethod
    def get(cls, name: str) -> Type:
        """도구 조회"""
        return cls._tools.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """등록된 모든 도구 목록"""
        return list(cls._tools.keys())

class ToolManager:
    """도구 관리자 (주입기)"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.active_tools: Dict[str, Any] = {}

    def inject(self, tool_names: List[str]) -> Dict[str, Any]:
        """도구 주입"""
        for name in tool_names:
            tool_class = ToolRegistry.get(name)
            if tool_class:
                self.active_tools[name] = tool_class()
        return self.active_tools

    def execute(self, tool_name: str, *args, **kwargs) -> Any:
        """도구 실행"""
        tool = self.active_tools.get(tool_name)
        if tool:
            return tool.execute(*args, **kwargs)
        raise ValueError(f"Tool not found: {tool_name}")
```

---

## 5. 설정 파일

### 5.1 페르소나 매핑 (config/personas.yaml)

```yaml
# personas.yaml - 페르소나 매핑 정의

personas:
  backend:
    name: "Backend Developer"
    description: "백엔드 개발 전문가"
    capabilities:
      - api_design
      - database_management
      - security_implementation
      - performance_optimization
    default_tools:
      - cli
      - database
      - api
    specialists:
      - api_designer
      - db_architect
      - security_auditor
      - performance_tuner

  frontend:
    name: "Frontend Developer"
    description: "프론트엔드 개발 전문가"
    capabilities:
      - ui_development
      - state_management
      - responsive_design
      - accessibility
    default_tools:
      - bundler
      - testing
      - linter
    specialists:
      - ui_designer
      - ux_analyst
      - accessibility_expert
      - performance_optimizer

  data:
    name: "Data Engineer"
    description: "데이터 엔지니어링 전문가"
    capabilities:
      - etl_pipeline
      - data_modeling
      - data_quality
      - lakehouse_architecture
    default_tools:
      - spark
      - airflow
      - dbt
    specialists:
      - etl_engineer
      - data_modeler
      - quality_analyst
      - pipeline_architect

  devops:
    name: "DevOps Engineer"
    description: "DevOps 전문가"
    capabilities:
      - ci_cd
      - infrastructure
      - monitoring
      - security_ops
    default_tools:
      - docker
      - kubernetes
      - terraform
      - ansible
    specialists:
      - ci_cd_engineer
      - infra_architect
      - sre_engineer
      - security_ops
```

### 5.2 라우팅 규칙 (config/routing.yaml)

```yaml
# routing.yaml - 도메인 라우팅 규칙

routing:
  rules:
    - pattern: "api|endpoint|rest|graphql"
      domain: backend
      workflow: api_design

    - pattern: "database|sql|migration|schema"
      domain: backend
      workflow: db_migration

    - pattern: "component|ui|react|vue|angular"
      domain: frontend
      workflow: component_design

    - pattern: "etl|pipeline|transform|data lake"
      domain: data
      workflow: etl_pipeline

    - pattern: "deploy|ci|cd|kubernetes|docker"
      domain: devops
      workflow: deployment

    - pattern: "monitor|alert|incident|sre"
      domain: devops
      workflow: monitoring_setup

  fallback:
    domain: backend
    workflow: general
```

### 5.3 역량 매트릭스 (config/capabilities.yaml)

```yaml
# capabilities.yaml - 역량 매트릭스

capabilities:
  backend:
    api_design:
      level: expert
      tools: [rest, graphql, openapi]
    database_management:
      level: expert
      tools: [postgresql, mysql, mongodb]
    security_implementation:
      level: advanced
      tools: [oauth, jwt, encryption]
    performance_optimization:
      level: advanced
      tools: [profiler, cache, load_testing]

  frontend:
    ui_development:
      level: expert
      tools: [react, vue, svelte]
    state_management:
      level: advanced
      tools: [redux, zustand, pinia]
    responsive_design:
      level: expert
      tools: [css, tailwind, styled_components]
    accessibility:
      level: intermediate
      tools: [axe, lighthouse, wave]

  data:
    etl_pipeline:
      level: expert
      tools: [spark, pandas, dbt]
    data_modeling:
      level: advanced
      tools: [dbt, erwin, datagrip]
    data_quality:
      level: advanced
      tools: [great_expectations, deequ]
    lakehouse_architecture:
      level: expert
      tools: [delta_lake, iceberg, hudi]

  devops:
    ci_cd:
      level: expert
      tools: [github_actions, jenkins, gitlab_ci]
    infrastructure:
      level: advanced
      tools: [terraform, pulumi, cloudformation]
    monitoring:
      level: advanced
      tools: [prometheus, grafana, datadog]
    security_ops:
      level: intermediate
      tools: [trivy, snyk, vault]
```

---

## 6. 실행 흐름

### 6.1 Think-Act Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Think-Act Loop Pattern                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────┐                                                               │
│   │  INPUT  │                                                               │
│   └────┬────┘                                                               │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │  INTENT ANALYZER                                                 │      │
│   │  "이 입력이 무엇을 원하는가?"                                      │      │
│   └────┬────────────────────────────────────────────────────────────┘      │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │  ROUTER                                                          │      │
│   │  "어떤 전문가/워크플로우가 처리해야 하는가?"                        │      │
│   └────┬────────────────────────────────────────────────────────────┘      │
│        │                                                                    │
│        ▼                                                                    │
│   ╔═════════════════════════════════════════════════════════════════╗      │
│   ║  SUB-WORKFLOW (Think-Tool Loop)                                  ║      │
│   ║                                                                  ║      │
│   ║   ┌──────────┐     ┌──────────┐     ┌──────────┐               ║      │
│   ║   │  THINK   │────►│   ACT    │────►│  OBSERVE │               ║      │
│   ║   │  (분석)   │     │  (실행)   │     │  (관찰)   │               ║      │
│   ║   └──────────┘     └──────────┘     └────┬─────┘               ║      │
│   ║        ▲                                  │                     ║      │
│   ║        │         ┌──────────────┐        │                     ║      │
│   ║        └─────────│  완료 여부?   │◄───────┘                     ║      │
│   ║                  └──────┬───────┘                              ║      │
│   ║                         │ Yes                                   ║      │
│   ╚═════════════════════════╪═══════════════════════════════════════╝      │
│                             ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │  RESULT AGGREGATOR                                               │      │
│   │  결과 취합 및 포맷팅                                               │      │
│   └────┬────────────────────────────────────────────────────────────┘      │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────┐                                                               │
│   │ OUTPUT  │                                                               │
│   └─────────┘                                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Main Orchestrator Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Main Orchestrator Flow                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Input                                                                │
│       │                                                                      │
│       ▼                                                                      │
│   ┌───────────────────┐                                                     │
│   │ Intent Analyzer   │──────► "api 설계 요청" / "DB 스키마 검토" / ...      │
│   └─────────┬─────────┘                                                     │
│             │                                                                │
│             ▼                                                                │
│   ┌───────────────────┐     ┌─────────────────────────────────────────┐    │
│   │    Router         │────►│ routing.yaml 규칙 적용                   │    │
│   └─────────┬─────────┘     └─────────────────────────────────────────┘    │
│             │                                                                │
│             ├──────────────────┬──────────────────┬───────────────────┐     │
│             ▼                  ▼                  ▼                   ▼     │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────┐ │
│   │ Backend Workflow│ │Frontend Workflow│ │  Data Workflow  │ │  DevOps  │ │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘ └──────────┘ │
│             │                  │                  │                   │     │
│             └──────────────────┴──────────────────┴───────────────────┘     │
│                                        │                                     │
│                                        ▼                                     │
│                              ┌─────────────────┐                            │
│                              │ Result Output   │                            │
│                              └─────────────────┘                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 확장 가이드

### 7.1 새 도메인 페르소나 추가

1. `personas/[NEW_DOMAIN]/` 디렉토리 생성
2. 5개 계층 폴더 구조 생성
3. `config/personas.yaml`에 도메인 추가
4. `config/routing.yaml`에 라우팅 규칙 추가

### 7.2 새 전문가 에이전트 추가

1. `personas/[DOMAIN]/agents/specialist/[NEW_SPECIALIST]/` 생성
2. `agent.py` 및 `prompts.py` 구현
3. `config/capabilities.yaml`에 역량 추가

### 7.3 새 워크플로우 추가

1. `personas/[DOMAIN]/workflow/sub/[NEW_WORKFLOW]/` 생성
2. `workflow.py`, `state.py`, `steps.yaml` 구현
3. 메인 오케스트레이터에 등록

---

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  📅 문서 생성일: 2026-02-01                                                   ║
║  🔖 버전: 1.0.0                                                               ║
║  📋 계층 수: 5개 (Agents, Workflow, Tools, Knowledge, Context)                ║
║  🎯 적용 도메인: Backend, Frontend, Data, DevOps, ML                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```
