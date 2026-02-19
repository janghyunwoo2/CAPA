"""
CAPA T2 Pipeline - Kubernetes Pod Operator 버전
각 Task를 독립적인 컨테이너에서 실행하는 예제
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from kubernetes.client import models as k8s

# DAG 기본 설정
default_args = {
    'owner': 'capa-t2-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# 공유 Volume 설정
volume_mount = k8s.V1VolumeMount(
    name='data-volume',
    mount_path='/data',
    sub_path=None,
    read_only=False
)

volume_config = k8s.V1Volume(
    name='data-volume',
    persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(
        claim_name='airflow-data-pvc'
    )
)

# 환경변수 설정
env_vars = {
    'AWS_DEFAULT_REGION': 'ap-northeast-2',
    'DATA_PATH': '/data',
    'LOG_LEVEL': 'INFO'
}

with DAG(
    'capa_t2_pipeline_kubernetes',
    default_args=default_args,
    description='CAPA T2 데이터 파이프라인 - K8s 버전',
    schedule_interval='@daily',
    catchup=False,
    tags=['capa', 't2', 'kubernetes'],
) as dag:
    
    # Task 1: 로그 생성
    generate_logs_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/log-generator:v1.0.0',
        name='generate-ad-logs',
        task_id='generate_logs',
        random_name_suffix=True,
        
        # 실행 명령
        cmds=['python'],
        arguments=['/app/generate_sample_logs.py', '--output-dir', '/data/raw'],
        
        # 환경변수
        env_vars={
            **env_vars,
            'NUM_DAYS': '7',
            'NUM_ROWS': '10000',
            'OUTPUT_FORMAT': 'parquet'
        },
        
        # 리소스 설정
        container_resources=k8s.V1ResourceRequirements(
            requests={
                'memory': '512Mi',
                'cpu': '250m'
            },
            limits={
                'memory': '1Gi',
                'cpu': '500m'
            }
        ),
        
        # Volume 마운트
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        
        # Pod 설정
        is_delete_operator_pod=True,
        get_logs=True,
        log_events_on_failure=True,
        
        # 보안 설정
        security_context={
            'runAsUser': 1000,
            'runAsGroup': 3000,
            'fsGroup': 2000,
            'runAsNonRoot': True
        },
        
        # 재시도 정책
        startup_timeout_seconds=120,
        
        # 노드 선택자 (선택사항)
        node_selector={
            'node-type': 'compute'
        },
        
        # 톨러레이션 (선택사항)
        tolerations=[
            k8s.V1Toleration(
                key='dedicated',
                operator='Equal',
                value='airflow',
                effect='NoSchedule'
            )
        ],
    )
    
    # Task 2: 데이터 처리
    process_data_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-processor:v1.0.0',
        name='process-ad-data',
        task_id='process_data',
        random_name_suffix=True,
        
        cmds=['python'],
        arguments=[
            '/app/processor.py',
            '--input-path', '/data/raw',
            '--output-path', '/data/processed'
        ],
        
        env_vars={
            **env_vars,
            'PROCESSING_MODE': 'batch',
            'PARALLELISM': '4'
        },
        
        # 더 많은 리소스 할당 (데이터 처리용)
        container_resources=k8s.V1ResourceRequirements(
            requests={
                'memory': '1Gi',
                'cpu': '500m'
            },
            limits={
                'memory': '2Gi',
                'cpu': '1000m'
            }
        ),
        
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        
        is_delete_operator_pod=True,
        get_logs=True,
        
        # Spark나 Pandas 사용 시 추가 설정
        # env_vars에 SPARK_CONF_DIR 등 추가 가능
    )
    
    # Task 3: 분석 리포트 생성
    analyze_data_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-analyzer:v1.0.0',
        name='analyze-ad-data',
        task_id='analyze_data',
        random_name_suffix=True,
        
        cmds=['python'],
        arguments=[
            '/app/analyzer.py',
            '--input-path', '/data/processed',
            '--output-path', '/data/analysis'
        ],
        
        env_vars={
            **env_vars,
            'ANALYSIS_TYPE': 'top_ads',
            'TOP_N': '20'
        },
        
        container_resources=k8s.V1ResourceRequirements(
            requests={
                'memory': '512Mi',
                'cpu': '250m'
            },
            limits={
                'memory': '1Gi',
                'cpu': '500m'
            }
        ),
        
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    # Task 4: 시각화
    visualize_data_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-visualizer:v1.0.0',
        name='visualize-ad-data',
        task_id='visualize_data',
        random_name_suffix=True,
        
        cmds=['python'],
        arguments=[
            '/app/visualize.py',
            '--input-path', '/data/processed',
            '--output-path', '/data/outputs'
        ],
        
        env_vars={
            **env_vars,
            'CHART_TYPES': 'line,bar',
            'OUTPUT_FORMAT': 'png'
        },
        
        # 시각화는 메모리를 더 많이 사용할 수 있음
        container_resources=k8s.V1ResourceRequirements(
            requests={
                'memory': '1Gi',
                'cpu': '500m'
            },
            limits={
                'memory': '2Gi',
                'cpu': '1000m'
            }
        ),
        
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        
        is_delete_operator_pod=True,
        get_logs=True,
        
        # matplotlib 백엔드 설정
        env_vars={
            **env_vars,
            'MPLBACKEND': 'Agg'  # GUI 없는 환경용
        }
    )
    
    # Task 5: S3 업로드 (선택사항)
    upload_to_s3_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/s3-uploader:v1.0.0',
        name='upload-results-s3',
        task_id='upload_to_s3',
        random_name_suffix=True,
        
        cmds=['python'],
        arguments=[
            '/app/s3_upload.py',
            '--local-path', '/data',
            '--s3-bucket', 'capa-data-pipeline',
            '--s3-prefix', '{{ ds }}'  # Airflow 템플릿 변수
        ],
        
        env_vars={
            **env_vars,
            'AWS_ACCESS_KEY_ID': '{{ var.value.aws_access_key }}',
            'AWS_SECRET_ACCESS_KEY': '{{ var.value.aws_secret_key }}'
        },
        
        container_resources=k8s.V1ResourceRequirements(
            requests={
                'memory': '256Mi',
                'cpu': '100m'
            },
            limits={
                'memory': '512Mi',
                'cpu': '200m'
            }
        ),
        
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        
        is_delete_operator_pod=True,
        get_logs=True,
        
        # S3 업로드는 실패해도 전체 파이프라인은 계속 진행
        trigger_rule='all_done',
    )
    
    # 의존성 설정
    generate_logs_task >> process_data_task >> analyze_data_task >> visualize_data_task >> upload_to_s3_task


# 병렬 처리 예제 (대용량 데이터 처리 시)
with DAG(
    'capa_t2_pipeline_parallel',
    default_args=default_args,
    description='CAPA T2 병렬 처리 파이프라인',
    schedule_interval='@daily',
    catchup=False,
    tags=['capa', 't2', 'kubernetes', 'parallel'],
) as parallel_dag:
    
    # 데이터를 여러 파티션으로 분할
    split_data_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-splitter:v1.0.0',
        name='split-data',
        task_id='split_data',
        cmds=['python'],
        arguments=['/app/split_data.py', '--partitions', '4'],
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    # 병렬로 처리할 Task들
    parallel_tasks = []
    for i in range(4):
        task = KubernetesPodOperator(
            namespace='airflow',
            image='capa/data-processor:v1.0.0',
            name=f'process-partition-{i}',
            task_id=f'process_partition_{i}',
            random_name_suffix=True,
            
            cmds=['python'],
            arguments=[
                '/app/processor.py',
                '--partition-id', str(i),
                '--total-partitions', '4'
            ],
            
            env_vars={
                **env_vars,
                'PARTITION_ID': str(i)
            },
            
            container_resources=k8s.V1ResourceRequirements(
                requests={
                    'memory': '512Mi',
                    'cpu': '250m'
                },
                limits={
                    'memory': '1Gi',
                    'cpu': '500m'
                }
            ),
            
            volume_mounts=[volume_mount],
            volumes=[volume_config],
            
            is_delete_operator_pod=True,
            get_logs=True,
            
            # Pod Anti-Affinity로 다른 노드에 분산
            affinity={
                'podAntiAffinity': {
                    'preferredDuringSchedulingIgnoredDuringExecution': [{
                        'weight': 100,
                        'podAffinityTerm': {
                            'labelSelector': {
                                'matchExpressions': [{
                                    'key': 'dag_id',
                                    'operator': 'In',
                                    'values': ['capa_t2_pipeline_parallel']
                                }]
                            },
                            'topologyKey': 'kubernetes.io/hostname'
                        }
                    }]
                }
            }
        )
        parallel_tasks.append(task)
    
    # 결과 병합
    merge_results_task = KubernetesPodOperator(
        namespace='airflow',
        image='capa/data-merger:v1.0.0',
        name='merge-results',
        task_id='merge_results',
        cmds=['python'],
        arguments=['/app/merge_results.py'],
        volume_mounts=[volume_mount],
        volumes=[volume_config],
        is_delete_operator_pod=True,
        get_logs=True,
    )
    
    # 의존성: split -> 병렬 처리 -> merge
    split_data_task >> parallel_tasks >> merge_results_task