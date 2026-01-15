#!/bin/bash
# E2E Smoke Test for ManualStudio
# Tests the full pipeline: upload → process → download
#
# Prerequisites:
#   - docker compose running (with mock providers)
#   - ffmpeg installed (for generating test video)
#   - curl, jq installed
#
# Usage:
#   ./scripts/e2e_smoke_test.sh [BASE_URL]
#   ./scripts/e2e_smoke_test.sh http://localhost:8000

set -e

BASE_URL="${1:-http://localhost:8000}"
TIMEOUT=120  # Max seconds to wait for job completion
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

echo "=== ManualStudio E2E Smoke Test ==="
echo "Base URL: $BASE_URL"
echo "Test directory: $TEST_DIR"

# 1. Check health endpoint
echo ""
echo "1. Checking health endpoint..."
HEALTH=$(curl -sf "$BASE_URL/health" || echo '{"status":"error"}')
if [ "$(echo "$HEALTH" | jq -r '.status')" != "ok" ]; then
    echo "ERROR: Health check failed"
    echo "$HEALTH"
    exit 1
fi
echo "   Health: OK"

# 2. Generate test video with ffmpeg
echo ""
echo "2. Generating test video..."
TEST_VIDEO="$TEST_DIR/test_video.mp4"

# Create a 5-second test video with color bars and silent audio
ffmpeg -y -f lavfi -i "testsrc=duration=5:size=640x480:rate=30" \
       -f lavfi -i "anullsrc=r=44100:cl=mono" \
       -c:v libx264 -preset ultrafast -crf 28 \
       -c:a aac -shortest \
       "$TEST_VIDEO" 2>/dev/null

if [ ! -f "$TEST_VIDEO" ]; then
    echo "ERROR: Failed to generate test video"
    exit 1
fi
VIDEO_SIZE=$(ls -lh "$TEST_VIDEO" | awk '{print $5}')
echo "   Generated: $TEST_VIDEO ($VIDEO_SIZE)"

# 3. Upload video and create job
echo ""
echo "3. Creating job (uploading video)..."
CREATE_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/jobs" \
    -F "video_file=@$TEST_VIDEO" \
    -F "title=E2E Smoke Test" \
    -F "goal=Testing the full pipeline" \
    -F "language=ja")

JOB_ID=$(echo "$CREATE_RESPONSE" | jq -r '.job_id')
if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
    echo "ERROR: Failed to create job"
    echo "$CREATE_RESPONSE"
    exit 1
fi
echo "   Job ID: $JOB_ID"

# 4. Poll for job completion
echo ""
echo "4. Waiting for job completion (timeout: ${TIMEOUT}s)..."
START_TIME=$(date +%s)
LAST_STAGE=""

while true; do
    ELAPSED=$(($(date +%s) - START_TIME))
    if [ $ELAPSED -gt $TIMEOUT ]; then
        echo "ERROR: Job timed out after ${TIMEOUT}s"
        exit 1
    fi

    JOB_STATUS=$(curl -sf "$BASE_URL/api/jobs/$JOB_ID")
    STATUS=$(echo "$JOB_STATUS" | jq -r '.status')
    STAGE=$(echo "$JOB_STATUS" | jq -r '.stage // "N/A"')
    PROGRESS=$(echo "$JOB_STATUS" | jq -r '.progress // 0')

    # Print stage changes
    if [ "$STAGE" != "$LAST_STAGE" ]; then
        echo "   [$ELAPSED s] Stage: $STAGE ($PROGRESS%)"
        LAST_STAGE="$STAGE"
    fi

    case "$STATUS" in
        "SUCCEEDED")
            echo "   Job completed successfully!"
            break
            ;;
        "FAILED")
            ERROR_MSG=$(echo "$JOB_STATUS" | jq -r '.error_message // "Unknown error"')
            ERROR_CODE=$(echo "$JOB_STATUS" | jq -r '.error_code // "UNKNOWN"')
            echo "ERROR: Job failed - $ERROR_CODE: $ERROR_MSG"
            exit 1
            ;;
        "CANCELED")
            echo "ERROR: Job was canceled"
            exit 1
            ;;
    esac

    sleep 2
done

# 5. Verify outputs
echo ""
echo "5. Verifying outputs..."

# Check steps.json
echo "   Checking steps.json..."
STEPS=$(curl -sf "$BASE_URL/api/jobs/$JOB_ID/steps")
STEPS_COUNT=$(echo "$STEPS" | jq '.steps_json.steps | length')
if [ "$STEPS_COUNT" -lt 1 ]; then
    echo "ERROR: No steps generated"
    exit 1
fi
echo "   Steps: $STEPS_COUNT steps generated"

# Check PPTX download
echo "   Checking PPTX download..."
PPTX_FILE="$TEST_DIR/output.pptx"
HTTP_CODE=$(curl -sf -w "%{http_code}" -L "$BASE_URL/api/jobs/$JOB_ID/download/pptx" -o "$PPTX_FILE")

# For redirect (307), we need to follow it
if [ "$HTTP_CODE" == "307" ] || [ "$HTTP_CODE" == "200" ]; then
    if [ -f "$PPTX_FILE" ] && [ -s "$PPTX_FILE" ]; then
        PPTX_SIZE=$(ls -lh "$PPTX_FILE" | awk '{print $5}')
        echo "   PPTX: Downloaded ($PPTX_SIZE)"
    else
        echo "   PPTX: Redirect returned (presigned URL - OK)"
    fi
else
    echo "ERROR: PPTX download failed (HTTP $HTTP_CODE)"
    exit 1
fi

# Check versions endpoint
echo "   Checking steps versions..."
VERSIONS=$(curl -sf "$BASE_URL/api/jobs/$JOB_ID/steps/versions")
VERSION_COUNT=$(echo "$VERSIONS" | jq '.versions | length')
echo "   Versions: $VERSION_COUNT version(s)"

# 6. Summary
echo ""
echo "=== E2E Smoke Test PASSED ==="
echo "Job ID: $JOB_ID"
echo "Steps: $STEPS_COUNT"
echo "Versions: $VERSION_COUNT"
echo "Duration: ${ELAPSED}s"
