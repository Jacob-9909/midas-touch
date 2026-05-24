#!/bin/bash

# =============================================================
# 1. 사용자 설정 정보 (여기에 설정값을 입력하세요)
# =============================================================
# 컴파트먼트 OCID (비워두거나 ocid1.* 형식이 아니면 루트/테넌시 OCID를 자동 조회합니다)
COMPARTMENT_ID=""

# 가상 클라우드 네트워크 및 서브넷 정보 (이름을 넣으면 자동으로 OCID를 조회합니다)
VCN_NAME="vcn-20260504-1032"
SUBNET_ID=""
SUBNET_NAME="subnet-20260504-1032"

# 가용성 도메인 (AD) 식별 키 (기본값 AD-1)
AD_IDENTIFIER="AD-1"
# 가용성 도메인 풀네임 (직접 풀네임을 입력해도 되며, 비워두면 AD_IDENTIFIER 기반 자동 조회합니다)
BACKGROUND_AD=""

# 이미지 사양 정보 (직접 이미지 OCID를 지정하거나, 비워두면 사양에 맞춰 자동 조회합니다)
IMAGE_ID=""
IMAGE_OS="Canonical Ubuntu"
IMAGE_OS_VERSION="22.04 Minimal"
IMAGE_BUILD="2026.04.30-1"

# SSH 공개 키 (생성할 인스턴스에 등록할 공개 키)
SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDGbLV7n3HTc+th2VKpp3hmdJ41db8dH78oSqlEFSyhCK4Y2OeQ9flSH2MUskGdaNYSG+nVW+oDCuVua9x31tG/S6JimXgExiVbEGWxaKwIiDpFSYJKk5JS8ImlETp5h3cb0942RWYtu8XG5M6ntAyrmExaSpPMWWvLp35byFB7qt1OJvNGG+FxCkm17JB7JTR/j6KlEhtH090GvyHCWa2DUpR0hX1GSbxh2KscFA003BvcEn46E3uW+OVUT9tupm4v+K1QNfFbfR5RsCk0WQ2mLs9Q7fdReSBaMLkUX1gQqdVuC4xSWbWexgw7vC/QJJTcNMj7CwI1HOd3xvdHz/gh ssh-key-2026-05-24"

# 인스턴스 사양 설정 (DB 전용 추천 사양: 2 OCPU / 12GB RAM / 100GB Boot Volume)
INSTANCE_NAME="instance-20260524-1412"
SHAPE="VM.Standard.A1.Flex"
OCPUS=1
MEMORY_IN_GBS=6
BOOT_VOLUME_SIZE_IN_GBS=100 # 오라클 Always Free는 총 200GB 부트 볼륨 무료 제공 (100~200GB 권장)

# =============================================================
# 2. OCI CLI 검증 및 리소스 OCID 동적 조회
# =============================================================
# OCI CLI 설치 확인
if ! command -v oci &> /dev/null; then
    echo "❌ 에러: oci CLI가 설치되어 있지 않습니다."
    echo "설치 및 설정 후에 다시 실행해주세요."
    exit 1
fi

# OCI CLI 로그인 상태 및 설정 파일 검증
HAS_CONFIG=true
if [ ! -f ~/.oci/config ] && [ -z "$OCI_CLI_CONFIG_FILE" ]; then
    HAS_CONFIG=false
fi

# 만약 설정 파일이 없고, 스크립트에도 직접 OCID들이 설정되어 있지 않다면 경고 및 안내 출력 후 종료
if [ "$HAS_CONFIG" = false ] && { [ -z "$COMPARTMENT_ID" ] || [ -z "$SUBNET_ID" ] || [ -z "$IMAGE_ID" ] || [ -z "$BACKGROUND_AD" ]; }; then
    echo "========================================================="
    echo "⚠️  OCI CLI 설정 파일(~/.oci/config)을 찾을 수 없습니다."
    echo "========================================================="
    echo "인스턴스 자동 생성을 시작하려면 다음 중 한 가지 방법을 수행해주세요:"
    echo ""
    echo "방법 1) 스크립트 상단의 '사용자 설정 정보' 변수들에 직접 OCID 값을 입력하십시오."
    echo "       - COMPARTMENT_ID=\"ocid1.tenancy.oc1..본인의_테넌시_OCID\""
    echo "       - SUBNET_ID=\"ocid1.subnet.oc1..본인의_서브넷_OCID\""
    echo "       - BACKGROUND_AD=\"gYXi:AP-SEOUL-1-AD-1\" (본인 리전의 AD 풀네임)"
    echo "       - IMAGE_ID=\"ocid1.image.oc1..본인의_우분투_이미지_OCID\""
    echo ""
    echo "방법 2) 터미널에 'oci setup config' 명령어를 입력하여 로그인 설정을 완료하십시오."
    echo "       설정을 마치면 스크립트가 리소스 정보를 자동으로 조회하여 매크로를 실행합니다."
    echo "========================================================="
    exit 1
fi

# OCI CLI 실행 후 빈 값이거나 에러 시 최대 3번 재시도하는 함수 (복제 지연 및 일시적 연결 실패 대비)
run_oci_query_with_retry() {
    local cmd="$1"
    local jq_expr="$2"
    local attempt=1
    local max_attempts=4
    local result=""
    
    while [ $attempt -lt $max_attempts ]; do
        result=$(eval "$cmd" 2>/dev/null | jq -r "$jq_expr" 2>/dev/null)
        if [ -n "$result" ] && [ "$result" != "null" ]; then
            echo "$result"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    return 1
}

echo "🔍 OCI 리소스 식별자(OCID) 조회 중..."

# 2-1. 컴파트먼트(루트/테넌시) OCID 확인
if [[ "$COMPARTMENT_ID" != ocid1.compartment.* ]] && [[ "$COMPARTMENT_ID" != ocid1.tenancy.* ]]; then
    echo " - 루트 컴파트먼트(테넌시) OCID 조회 중..."
    COMPARTMENT_ID=$(grep -E "^tenancy\s*=" ~/.oci/config 2>/dev/null | cut -d'=' -f2 | tr -d '[:space:]')
    if [ -z "$COMPARTMENT_ID" ]; then
        echo "❌ 에러: 컴파트먼트(테넌시) OCID를 조회할 수 없습니다."
        echo "스크립트 상단의 COMPARTMENT_ID 변수에 직접 OCID를 입력해주세요."
        exit 1
    fi
    echo "   📍 컴파트먼트 OCID: $COMPARTMENT_ID"
fi

# 2-2. 가용성 도메인(AD) 이름 확인
if [[ "$BACKGROUND_AD" != *:* ]]; then
    echo " - 가용성 도메인($AD_IDENTIFIER) 조회 중..."
    BACKGROUND_AD=$(run_oci_query_with_retry "oci iam availability-domain list --compartment-id \"$COMPARTMENT_ID\"" ".data[] | select(.name | endswith(\"-$AD_IDENTIFIER\")) | .name" | head -n1)
    if [ -z "$BACKGROUND_AD" ] || [ "$BACKGROUND_AD" = "null" ]; then
        BACKGROUND_AD="shrd:AP-TOKYO-1-AD-1"
        echo "   ⚠️  가용성 도메인 조회 실패. 기본값(도쿄 AD-1)으로 설정: $BACKGROUND_AD"
    else
        echo "   📍 가용성 도메인: $BACKGROUND_AD"
    fi
fi

# 2-3. 서브넷 OCID 확인
if [[ "$SUBNET_ID" != ocid1.subnet.* ]]; then
    echo " - 가상 클라우드 네트워크($VCN_NAME) 조회 중..."
    VCN_ID=$(run_oci_query_with_retry "oci network vcn list --compartment-id \"$COMPARTMENT_ID\"" ".data[] | select(.\"display-name\" == \"$VCN_NAME\") | .id" | head -n1)
    
    if [ -z "$VCN_ID" ] || [ "$VCN_ID" = "null" ]; then
        echo "   ⚠️  가상 클라우드 네트워크 '$VCN_NAME'을 찾을 수 없어 서브넷 전체 검색을 진행합니다."
        SUBNET_ID=$(run_oci_query_with_retry "oci network subnet list --compartment-id \"$COMPARTMENT_ID\"" ".data[] | select(.\"display-name\" == \"$SUBNET_NAME\") | .id" | head -n1)
    else
        echo "   📍 VCN OCID: $VCN_ID"
        echo " - 서브넷($SUBNET_NAME) OCID 조회 중..."
        SUBNET_ID=$(run_oci_query_with_retry "oci network subnet list --compartment-id \"$COMPARTMENT_ID\" --vcn-id \"$VCN_ID\"" ".data[] | select(.\"display-name\" == \"$SUBNET_NAME\") | .id" | head -n1)
    fi

    if [ -z "$SUBNET_ID" ] || [ "$SUBNET_ID" = "null" ]; then
        # 최종 폴백: VCN 지정 없이 서브넷 리스트 필터링 적용 시도
        SUBNET_ID=$(oci network subnet list --compartment-id "$COMPARTMENT_ID" --display-name "$SUBNET_NAME" --query "data[0].id" --raw-output 2>/dev/null)
    fi

    if [ -z "$SUBNET_ID" ] || [ "$SUBNET_ID" = "null" ]; then
        echo "❌ 에러: 서브넷명 '$SUBNET_NAME'에 해당하는 OCID를 조회할 수 없습니다."
        echo "스크립트 상단의 SUBNET_ID 변수에 직접 OCID를 입력해주세요."
        exit 1
    fi
    echo "   📍 서브넷 OCID: $SUBNET_ID"
fi

# 2-4. 이미지 OCID 확인
if [[ "$IMAGE_ID" != ocid1.image.* ]]; then
    echo " - Canonical Ubuntu 22.04 Minimal aarch64 이미지 OCID 조회 중..."
    
    # 1순위: 'Ubuntu', 'Minimal', '22.04', 빌드 버전($IMAGE_BUILD)이 모두 포함된 ARM 이미지 검색
    IMAGE_ID=$(run_oci_query_with_retry "oci compute image list --compartment-id \"$COMPARTMENT_ID\" --shape \"$SHAPE\"" ".data[] | select(.\"display-name\" | contains(\"Ubuntu\") and contains(\"Minimal\") and contains(\"22.04\") and contains(\"$IMAGE_BUILD\")) | .id" | head -n1)
    
    # 2순위: 'Ubuntu', 'Minimal', '22.04'가 포함된 가장 최신 ARM 이미지 검색
    if [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "null" ]; then
        IMAGE_ID=$(run_oci_query_with_retry "oci compute image list --compartment-id \"$COMPARTMENT_ID\" --shape \"$SHAPE\"" ".data[] | select(.\"display-name\" | contains(\"Ubuntu\") and contains(\"Minimal\") and contains(\"22.04\")) | .id" | head -n1)
    fi
    
    # 3순위: 'Ubuntu', 'Minimal'이 포함된 가장 최신 ARM 이미지 검색 (최종 폴백)
    if [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "null" ]; then
        IMAGE_ID=$(run_oci_query_with_retry "oci compute image list --compartment-id \"$COMPARTMENT_ID\" --shape \"$SHAPE\"" ".data[] | select(.\"display-name\" | contains(\"Ubuntu\") and contains(\"Minimal\")) | .id" | head -n1)
    fi
    
    if [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "null" ]; then
        echo "❌ 에러: 조건에 맞는 이미지 OCID를 조회할 수 없습니다."
        echo "스크립트 상단의 IMAGE_ID 변수에 직접 이미지 OCID를 입력해주세요."
        exit 1
    fi
    echo "   📍 이미지 OCID: $IMAGE_ID"
fi

# =============================================================
# 3. 매크로 루프 시작
# =============================================================
COUNT=1

echo ""
echo "🚀 오라클 클라우드 ARM 인스턴스 자동 생성 매크로를 시작합니다."
echo "   - 이름: $INSTANCE_NAME"
echo "   - 가용성 도메인: $BACKGROUND_AD"
echo "   - 사양: $SHAPE ($OCPUS OCPU, $MEMORY_IN_GBS GB RAM)"
echo "   - 디스크: 부트 볼륨 크기 ${BOOT_VOLUME_SIZE_IN_GBS}GB"
echo "   - 네트워크: 퍼블릭 IP 할당함"
echo "---------------------------------------------------------"

while true
do
    echo -n "[$COUNT 회차] 인스턴스 생성 시도 중..."
    
    # 생성 명령 수행 및 에러 메시지 캡처
    RESPONSE=$(oci compute instance launch \
        --availability-domain "$BACKGROUND_AD" \
        --compartment-id "$COMPARTMENT_ID" \
        --shape "$SHAPE" \
        --shape-config "{\"ocpus\":$OCPUS, \"memoryInGBs\":$MEMORY_IN_GBS}" \
        --boot-volume-size-in-gbs "$BOOT_VOLUME_SIZE_IN_GBS" \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --display-name "$INSTANCE_NAME" \
        --metadata "{\"ssh_authorized_keys\": \"$SSH_PUBLIC_KEY\"}" 2>&1)
    EXIT_CODE=$?
    RESPONSE_LOWER=$(echo "$RESPONSE" | tr '[:upper:]' '[:lower:]')

    # 결과 판독
    if [ $EXIT_CODE -eq 0 ]; then
        echo " -> 결과 확인 필요!"
        echo "$RESPONSE"
        # JSON 결과에서 실제로 생성된 인스턴스의 ID 추출 및 확인
        INSTANCE_ID_RESULT=$(echo "$RESPONSE" | jq -r '.data.id' 2>/dev/null)
        if [ -n "$INSTANCE_ID_RESULT" ] && [ "$INSTANCE_ID_RESULT" != "null" ]; then
            echo "🎉 인스턴스 생성에 성공했습니다! (인스턴스 ID: $INSTANCE_ID_RESULT)"
            break
        fi
        sleep 60
    elif [[ $RESPONSE_LOWER == *"capacity"* ]] || [[ $RESPONSE_LOWER == *"timed out"* ]] || [[ $RESPONSE_LOWER == *"connection"* ]] || [[ $RESPONSE_LOWER == *"timeout"* ]] || [[ $RESPONSE_LOWER == *"resolve"* ]] || [[ $RESPONSE == *"LimitExceeded"* ]]; then
        echo " -> 실패 (자원 부족 또는 네트워크 지연). 30초 대기..."
        COUNT=$((COUNT+1))
        sleep 30
    else
        echo " -> 실패 (에러 발생). 60초 대기..."
        echo "$RESPONSE"
        COUNT=$((COUNT+1))
        sleep 60
    fi
done