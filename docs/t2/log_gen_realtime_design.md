# 실시간 광고 로그 생성기 설계 가이드

## 1. 개요

기존의 배치 방식 로그 생성기를 실시간 스트리밍 방식으로 전환하여, 실제 서비스와 유사한 불규칙한 트래픽 패턴을 생성하고 Kinesis Data Streams와 Firehose를 통해 S3에 실시간으로 저장합니다.

## 2. 아키텍처 비교

### 2.1 기존 배치 방식
```
[시간별 배치 생성] → [DataFrame 구성] → [Parquet 압축] → [S3 직접 저장]
```
- 1시간 단위로 10,000개 이상의 로그를 한번에 생성
- 메모리에 모든 데이터를 보관 후 저장
- 실제 서비스와 다른 인위적인 패턴

### 2.2 실시간 스트리밍 방식
```
[실시간 이벤트 발생] → [JSON 직렬화] → [Kinesis Streams] → [Firehose] → [S3]
```
- 개별 이벤트가 불규칙하게 발생
- 즉시 Kinesis로 전송
- 실제 사용자 행동 패턴 시뮬레이션

## 3. 실시간 트래픽 패턴 설계

### 3.1 시간대별 트래픽 패턴

```python
class TrafficPattern:
    """실시간 트래픽 패턴 생성기"""
    
    @staticmethod
    def get_events_per_second(current_time: datetime) -> float:
        """현재 시간에 따른 초당 이벤트 수 계산"""
        hour = current_time.hour
        minute = current_time.minute
        weekday = current_time.weekday()
        
        # 기본 초당 이벤트 수
        base_rate = 10.0  # 초당 10개 기준
        
        # 시간대별 가중치
        hour_weights = {
            (0, 6): 0.2,    # 새벽: 20%
            (6, 9): 0.8,    # 아침: 80%
            (9, 11): 0.6,   # 오전: 60%
            (11, 14): 2.0,  # 점심: 200%
            (14, 17): 0.7,  # 오후: 70%
            (17, 21): 2.5,  # 저녁: 250%
            (21, 24): 1.2   # 밤: 120%
        }
        
        # 요일별 가중치
        day_weight = 1.0
        if weekday >= 4:  # 금토일
            day_weight = 1.5
        
        # 랜덤 스파이크 (5% 확률로 3-5배 트래픽)
        spike = 1.0
        if random.random() < 0.05:
            spike = random.uniform(3, 5)
        
        # 분단위 변동성 추가 (±20%)
        minute_variation = 1.0 + (math.sin(minute * 6) * 0.2)
        
        # 최종 계산
        for time_range, weight in hour_weights.items():
            if time_range[0] <= hour < time_range[1]:
                return base_rate * weight * day_weight * spike * minute_variation
        
        return base_rate
```

### 3.2 사용자 행동 시뮬레이션

```python
class UserBehaviorSimulator:
    """실제 사용자 행동 패턴 시뮬레이션"""
    
    def __init__(self):
        self.active_sessions = {}  # 활성 세션 추적
        self.user_states = {}      # 사용자별 상태 관리
    
    def simulate_user_journey(self, user_id: str) -> Generator[Dict, None, None]:
        """사용자의 전체 여정 시뮬레이션"""
        
        # 1. 첫 노출 (홈페이지 진입)
        yield self.create_impression(user_id, "home_top_rolling")
        
        # 2. 추가 노출 (스크롤하며 광고 확인)
        if random.random() < 0.7:  # 70% 사용자가 스크롤
            time.sleep(random.uniform(2, 5))
            yield self.create_impression(user_id, "list_middle")
        
        # 3. 검색 후 노출
        if random.random() < 0.3:  # 30% 사용자가 검색
            time.sleep(random.uniform(3, 10))
            yield self.create_impression(user_id, "search_ai_recommend")
        
        # 4. 클릭 발생
        if random.random() < 0.12:  # 12% CTR
            time.sleep(random.uniform(0.5, 3))
            click = self.create_click(user_id)
            yield click
            
            # 5. 전환 발생
            if random.random() < 0.08:  # 8% CVR
                time.sleep(random.uniform(5, 30))
                yield self.create_conversion(user_id, click["click_id"])
```

## 4. 실시간 로그 생성기 구현

### 4.1 메인 생성기 클래스

```python
import asyncio
import json
import random
import uuid
from datetime import datetime
from typing import Dict, Optional
import boto3
from concurrent.futures import ThreadPoolExecutor

class RealtimeAdLogGenerator:
    """실시간 광고 로그 생성기"""
    
    def __init__(self):
        # Kinesis 클라이언트
        self.kinesis_client = boto3.client(
            'kinesis',
            region_name='ap-northeast-2'
        )
        self.stream_name = "capa-ad-logs-stream"
        
        # 트래픽 패턴 및 행동 시뮬레이터
        self.traffic_pattern = TrafficPattern()
        self.behavior_simulator = UserBehaviorSimulator()
        
        # 스레드 풀 (병렬 처리)
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # 통계
        self.stats = {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "errors": 0
        }
    
    async def generate_event(self):
        """단일 이벤트 생성 및 전송"""
        try:
            # 새로운 사용자 또는 기존 사용자 선택
            if random.random() < 0.3 or not self.behavior_simulator.active_sessions:
                # 30% 확률로 새 사용자
                user_id = f"user_{random.randint(1, 100000):06d}"
            else:
                # 70% 확률로 기존 활성 사용자
                user_id = random.choice(list(self.behavior_simulator.active_sessions.keys()))
            
            # 사용자 여정 시뮬레이션
            for event in self.behavior_simulator.simulate_user_journey(user_id):
                await self.send_to_kinesis(event)
                
                # 통계 업데이트
                event_type = event.get("event_type")
                if event_type == "impression":
                    self.stats["impressions"] += 1
                elif event_type == "click":
                    self.stats["clicks"] += 1
                elif event_type == "conversion":
                    self.stats["conversions"] += 1
                    
        except Exception as e:
            self.stats["errors"] += 1
            print(f"Error generating event: {e}")
    
    async def send_to_kinesis(self, event: Dict):
        """Kinesis로 이벤트 전송"""
        try:
            # 타임스탬프 추가
            event["timestamp"] = datetime.now().isoformat()
            event["event_id"] = str(uuid.uuid4())
            
            # Kinesis 전송
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.kinesis_client.put_record(
                    StreamName=self.stream_name,
                    Data=json.dumps(event, ensure_ascii=False) + '\n',
                    PartitionKey=event.get("user_id", "default")
                )
            )
            
            # 디버그 출력
            if random.random() < 0.01:  # 1% 샘플링
                print(f"[{event['timestamp']}] {event['event_type']} - User: {event['user_id']}")
                
        except Exception as e:
            print(f"Kinesis send error: {e}")
            raise
    
    async def run(self):
        """실시간 로그 생성 실행"""
        print("🚀 실시간 광고 로그 생성기 시작")
        print(f"Target stream: {self.stream_name}")
        
        # 통계 출력 태스크
        asyncio.create_task(self.print_stats_periodically())
        
        while True:
            try:
                # 현재 시간의 트래픽 패턴에 따른 이벤트 생성
                current_time = datetime.now()
                events_per_second = self.traffic_pattern.get_events_per_second(current_time)
                
                # 포아송 분포로 실제 이벤트 수 결정 (더 자연스러운 분포)
                actual_events = np.random.poisson(events_per_second)
                
                # 병렬로 이벤트 생성
                tasks = []
                for _ in range(actual_events):
                    tasks.append(asyncio.create_task(self.generate_event()))
                
                # 1초 대기 (다음 초로)
                await asyncio.sleep(1)
                
                # 생성된 태스크 완료 대기 (비동기)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
            except KeyboardInterrupt:
                print("\n종료 신호 수신...")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                await asyncio.sleep(1)
    
    async def print_stats_periodically(self):
        """주기적으로 통계 출력"""
        while True:
            await asyncio.sleep(60)  # 1분마다
            
            total = sum(self.stats.values()) - self.stats["errors"]
            if total > 0:
                ctr = (self.stats["clicks"] / self.stats["impressions"] * 100) if self.stats["impressions"] > 0 else 0
                cvr = (self.stats["conversions"] / self.stats["clicks"] * 100) if self.stats["clicks"] > 0 else 0
                
                print(f"\n📊 통계 (최근 1분):")
                print(f"  노출: {self.stats['impressions']:,}")
                print(f"  클릭: {self.stats['clicks']:,} (CTR: {ctr:.2f}%)")
                print(f"  전환: {self.stats['conversions']:,} (CVR: {cvr:.2f}%)")
                print(f"  에러: {self.stats['errors']:,}")
                print(f"  초당 평균: {total/60:.1f} events/sec\n")
```

### 4.2 실행 스크립트

```python
# main.py
import asyncio
from realtime_generator import RealtimeAdLogGenerator

async def main():
    generator = RealtimeAdLogGenerator()
    await generator.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## 5. Firehose 설정

### 5.1 자동 배치 처리
```yaml
firehose_configuration:
  # 버퍼 설정 - 실시간성과 효율성의 균형
  buffer_conditions:
    size_in_mbs: 5         # 5MB마다
    interval_in_seconds: 60 # 또는 60초마다 S3로 전송
  
  # 동적 파티셔닝
  dynamic_partitioning:
    enabled: true
    retry_duration: 3600
```

### 5.2 데이터 변환
- JSON → Parquet 자동 변환
- 타임스탬프 기반 파티셔닝
- 압축 (GZIP/Snappy)

## 6. 주요 특징

### 6.1 실시간성
- 이벤트 발생 즉시 Kinesis로 전송
- 1-2초 내 스트림에 도달
- Firehose가 자동으로 배치 처리하여 S3 저장

### 6.2 자연스러운 트래픽 패턴
- 시간대별/요일별 변동
- 랜덤 스파이크 발생
- 포아송 분포 기반 이벤트 생성
- 실제 사용자 행동 시뮬레이션

### 6.3 확장성
- 비동기 처리로 높은 처리량
- Kinesis 샤드 자동 확장
- 병렬 이벤트 생성

### 6.4 모니터링
- 실시간 통계 출력
- CloudWatch 메트릭 연동
- 에러 추적 및 복구

## 7. 환경 변수 설정

```bash
# .env
AWS_REGION=ap-northeast-2
KINESIS_STREAM_NAME=capa-ad-logs-stream
BASE_EVENTS_PER_SECOND=10
ENABLE_DEBUG=false
STATS_INTERVAL_SECONDS=60
```

## 8. 실행 방법

### 8.1 로컬 실행
```bash
# 환경 설정
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install boto3 numpy faker python-dotenv

# 실행
python main.py
```

### 8.2 Docker 실행
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t realtime-log-generator .
docker run --env-file .env realtime-log-generator
```

### 8.3 ECS/Fargate 배포
- 항상 실행되는 서비스로 배포
- Auto Scaling 설정으로 부하 대응
- 다중 태스크로 트래픽 증대 가능

## 9. 장점

1. **실제와 유사한 데이터**: 배치가 아닌 실시간 이벤트 스트림
2. **자연스러운 패턴**: 시간대별 변동, 사용자 행동 시뮬레이션
3. **확장 가능**: 트래픽 증가에 따라 자동 확장
4. **모니터링 용이**: 실시간 메트릭과 통계
5. **유연한 배포**: 로컬, Docker, ECS 등 다양한 환경 지원

## 10. 마이그레이션 계획

### Phase 1: 개발 환경 테스트 (1주)
- 실시간 생성기 개발 및 테스트
- Kinesis/Firehose 설정 검증
- 성능 및 비용 분석

### Phase 2: 병렬 운영 (1주)
- 기존 배치 생성기와 병렬 실행
- 데이터 일관성 검증
- 다운스트림 시스템 호환성 확인

### Phase 3: 전환 (3일)
- 실시간 생성기로 완전 전환
- 모니터링 강화
- 성능 최적화