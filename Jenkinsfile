pipeline {

  agent any

  options {
    buildDiscarder(logRotator(numToKeepStr: '10'))
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    IMAGE = "orivdev/oriv-mcp"
    VERSION = "${env.BUILD_NUMBER}"
    SAFE_BRANCH = "${env.BRANCH_NAME}".replaceAll('[^a-zA-Z0-9_.-]', '-')
    FULL_IMAGE = "${IMAGE}-${SAFE_BRANCH}"
    FULL_IMAGE_VERSION = "${FULL_IMAGE}:${VERSION}"
    TEAMS_WEBHOOK = credentials('TEAMS_WEBHOOK')
    DEFECTDOJO_URL = credentials('defectdojo-url')
    DEFECTDOJO_TOKEN = credentials('defectdojo-token')
    SONAR_TOKEN = credentials('SONAR_TOKEN')
    SONAR_URL = credentials('SONAR_URL')
    SONAR_PROJECT_KEY = credentials('SONAR_PROJECT_KEY')
    SERVER_USER = credentials('SERVER_USER')
    SERVER_PASS = credentials('SERVER_PASS')
    SERVER_IP = credentials('SERVER_IP')
    SERVICE = credentials('SERVICE')
    SERVICE_DEV = credentials('SERVICE_DEV')

    DOCKER_BUILDKIT = "1"
    BUILDER = "secure-builder"
  }

  stages {

    stage('Build & Security') {
      options { timeout(time: 1, unit: 'HOURS') }
      parallel {

        stage('Build Verification') {
          agent {
            docker {
            image 'python:3.12-slim'
            args '-u root --cpus=1'
            }
          }
          steps {
            sh '''
              set -eux

              # Install required OS packages
              apt-get update
              apt-get install -y curl ca-certificates git

              # Install uv
              curl -LsSf https://astral.sh/uv/install.sh | sh

              # Load uv into PATH
              export PATH="$HOME/.local/bin:$PATH"

              uv --version

              # Install Python
              uv python install 3.12

              # Temporary fix for failing dependency build
              if [ -d "deps/lib-oriv-agents-sdk/deps/lib-oriv-tools" ]; then
                  touch deps/lib-oriv-agents-sdk/deps/lib-oriv-tools/README.md
              fi

              # Install dependencies
              uv sync --locked --dev
            '''
          }
        }

        stage('Dependency Security Audit') {
          agent {
            docker {
              image 'aquasec/trivy:0.69.3'
              args '-u root --entrypoint="" --cpus=1'
            }
          }

          steps {
            sh '''
              set +e
              export TRIVY_DISABLE_VEX_NOTICE=true

              apk add --no-cache jq curl

              echo "Running Trivy scan (CRITICAL only)..."

              trivy fs . \
                --scanners vuln \
                --severity CRITICAL \
                --format json \
                -o output.json

              CRITICAL=$(jq '[.Results[].Vulnerabilities[]?] | length' output.json)

              echo "Critical vulnerabilities found: $CRITICAL"

              case "$BRANCH_NAME" in
                dev)
                  ENVIRONMENT="dev"
                  ENGAGEMENT="54"
                  ;;
                qa)
                  ENVIRONMENT="qa"
                  ENGAGEMENT="55"
                  ;;
                *)
                  ENVIRONMENT="dev"
                  ENGAGEMENT="54"
                  ;;
              esac

              if [ "$CRITICAL" -gt 0 ]; then

                echo "Uploading CRITICAL vulnerabilities to DefectDojo..."

                curl -s -X POST "$DEFECTDOJO_URL/api/v2/import-scan/" \
                  -H "Authorization: Token $DEFECTDOJO_TOKEN" \
                  -F "scan_type=Trivy Scan" \
                  -F "file=@output.json" \
                  -F "engagement=$ENGAGEMENT" \
                  -F "environment=$ENVIRONMENT" \
                  -F "active=true" \
                  -F "verified=true" \
                  -F "close_old_findings=true"

                TIMESTAMP=$(TZ="Asia/Kolkata" date +"%Y-%m-%d %I:%M:%S %p IST")

                jq -n \
                  --arg job "$JOB_NAME" \
                  --arg build "$BUILD_NUMBER" \
                  --arg branch "$BRANCH_NAME" \
                  --arg repository "$GIT_URL" \
                  --arg critical "$CRITICAL" \
                  --arg time "$TIMESTAMP" \
                  --arg url "$BUILD_URL" \
                '
                {
                  type: "message",
                  attachments: [{
                    contentType: "application/vnd.microsoft.card.adaptive",
                    content: {
                      "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                      type: "AdaptiveCard",
                      version: "1.4",
                      body: [
                        {
                          type: "TextBlock",
                          text: "🚨 CRITICAL Vulnerabilities Detected",
                          weight: "Bolder",
                          size: "Large",
                          color: "Attention"
                        },
                        {
                          type: "FactSet",
                          facts: [
                            {title:"Job",value:$job},
                            {title:"Build",value:$build},
                            {title:"Branch",value:$branch},
                            {title:"Repository",value:$repository},
                            {title:"Critical Vulnerabilities",value:$critical},
                            {title:"Time",value:$time}
                          ]
                        }
                      ],
                      actions: [{
                        type: "Action.OpenUrl",
                        title: "View Build",
                        url: $url
                      }]
                    }
                  }]
                }
                ' > teams.json

                echo "Sending Teams alert..."

                curl -s \
                  -H "Content-Type: application/json" \
                  -d @teams.json \
                  $TEAMS_WEBHOOK

                echo "Failing pipeline because CRITICAL vulnerabilities exist."
                exit 1
              fi

              echo "No CRITICAL vulnerabilities found. Continuing pipeline."
            '''
          }

          post {
            always {
              archiveArtifacts artifacts: 'output.json', fingerprint: true
            }
          }
        }
      
        stage('Code Quality Gate') {
          agent {
            docker {
              image 'sonarsource/sonar-scanner-cli'
              args '--entrypoint="" --cpus=1'
            }
          }
          steps {
            checkout scm
            withCredentials([string(credentialsId: 'SONAR_TOKEN', variable: 'SONAR_TOKEN')]) {
              sh '''
                sonar-scanner \
                  -Dsonar.projectKey="${SONAR_PROJECT_KEY}" \
                  -Dsonar.host.url="${SONAR_URL}" \
                  -Dsonar.token="${SONAR_TOKEN}" \
                  -Dsonar.sources=oriv_mcp \
                  -Dsonar.exclusions=**/__pycache__/**,**/.venv/**,**/venv/**,**/build/**,**/dist/**
              '''
            }
          }
        }

        stage('SAST Scan') {
          agent {
            docker {
              image 'semgrep/semgrep:latest'
              args "--entrypoint='' -u root --cpus=1"
            }
          }

          steps {
            checkout scm

            sh '''
              set +e

              apk add --no-cache jq curl

              echo "=== Running Semgrep SAST scan ==="

              semgrep scan . \
                --config auto \
                --no-git-ignore \
                --include="*.ts" \
                --include="*.js" \
                --include="*.json" \
                --max-target-bytes 5000000 \
                --sarif \
                --output semgrep.sarif \
                --verbose | tee semgrep.log || true


              case "$BRANCH_NAME" in
                dev)
                  ENVIRONMENT="dev"
                  ENGAGEMENT="54"
                  ;;
                qa)
                  ENVIRONMENT="qa"
                  ENGAGEMENT="55"
                  ;;
                *)
                  ENVIRONMENT="dev"
                  ENGAGEMENT="54"
                  ;;
              esac


              echo "Uploading findings to DefectDojo..."

              DD_RESPONSE=$(curl -s -X POST "$DEFECTDOJO_URL/api/v2/import-scan/" \
                -H "Authorization: Token $DEFECTDOJO_TOKEN" \
                -F "scan_type=SARIF" \
                -F "file=@semgrep.sarif" \
                -F "engagement=$ENGAGEMENT" \
                -F "environment=$ENVIRONMENT" \
                -F "active=true" \
                -F "verified=true" \
                -F "close_old_findings=true")

              echo "$DD_RESPONSE" > dojo-response.json


              echo "=== SAST Results (DefectDojo) ==="

              HIGH=$(jq '.statistics.after.high.total' dojo-response.json)
              MEDIUM=$(jq '.statistics.after.medium.total' dojo-response.json)
              LOW=$(jq '.statistics.after.low.total' dojo-response.json)
              TOTAL=$(jq '.statistics.after.total.total' dojo-response.json)

              echo "Total: $TOTAL"
              echo "High: $HIGH"
              echo "Medium: $MEDIUM"
              echo "Low: $LOW"


              if [ "$HIGH" -gt 0 ]; then

                echo "High SAST vulnerabilities detected."

                TIMESTAMP=$(TZ="Asia/Kolkata" date +"%Y-%m-%d %I:%M:%S %p IST")

                jq -n \
                  --arg job "$JOB_NAME" \
                  --arg build "$BUILD_NUMBER" \
                  --arg branch "$BRANCH_NAME" \
                  --arg repository "$GIT_URL" \
                  --arg high "$HIGH" \
                  --arg medium "$MEDIUM" \
                  --arg low "$LOW" \
                  --arg time "$TIMESTAMP" \
                  --arg url "$BUILD_URL" \
                '
                {
                  type: "message",
                  attachments: [{
                    contentType: "application/vnd.microsoft.card.adaptive",
                    content: {
                      "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                      type: "AdaptiveCard",
                      version: "1.4",
                      body: [
                        {
                          type: "TextBlock",
                          text: "🚨 High SAST Vulnerabilities Detected",
                          weight: "Bolder",
                          size: "Large",
                          color: "Attention"
                        },
                        {
                          type: "FactSet",
                          facts: [
                            {title:"Job",value:$job},
                            {title:"Build",value:$build},
                            {title:"Branch",value:$branch},
                            {title:"Repository",value:$repository},
                            {title:"High",value:$high},
                            {title:"Medium",value:$medium},
                            {title:"Low",value:$low},
                            {title:"Time",value:$time}
                          ]
                        }
                      ],
                      actions: [{
                        type: "Action.OpenUrl",
                        title: "View Build",
                        url: $url
                      }]
                    }
                  }]
                }
                ' > sast-teams.json


                echo "Sending Teams alert..."

                curl -s \
                  -H "Content-Type: application/json" \
                  -d @sast-teams.json \
                  $TEAMS_WEBHOOK


                echo "Failing pipeline because HIGH vulnerabilities exist."
                exit 1
              fi


              echo "No High vulnerabilities. Pipeline continues."

            '''
          }

          post {
            always {
              archiveArtifacts artifacts: 'semgrep.sarif,semgrep.log,dojo-response.json', allowEmptyArchive: true
              stash name: 'semgrep-results', includes: 'semgrep.sarif', allowEmpty: true
            }
          }
        }

      }
    }

    stage('Check Time Approval') {
      steps {
        script {

          def hour = new Date().format("H", TimeZone.getTimeZone('Asia/Kolkata')) as int

          if (hour >= 18  || hour < 8) {
            sh """
              curl -H "Content-Type: application/json" \\
              -d '{
                "type": "message",
                "attachments": [{
                  "contentType": "application/vnd.microsoft.card.adaptive",
                  "content": {
                    "\$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                      {
                        "type": "TextBlock",
                        "text": "⏳ Build Waiting for DevOps Approval",
                        "weight": "Bolder",
                        "size": "Large",
                        "color": "Warning"
                      },
                      {
                        "type": "FactSet",
                        "facts": [
                          {"title":"Job","value":"${env.JOB_NAME}"},
                          {"title":"Build","value":"${env.BUILD_NUMBER}"},
                          {"title":"Branch","value":"${env.BRANCH_NAME}"},
                          {"title":"Repository","value":"${env.GIT_URL}"}
                        ]
                      },
                      {
                        "type": "TextBlock",
                        "text": "Build triggered after 6PM and requires DevOps approval.",
                        "wrap": true
                      }
                    ],
                  }
                }]
              }' \\
              "$TEAMS_WEBHOOK"
            """
            input message: 'Build requested after 6PM. DevOps approval required', submitter: 'devops_user'
          }
        }
      }
    }

    stage('Build & Push') {
      options { timeout(time: 1, unit: 'HOURS') }
      when {
        anyOf {
          branch 'dev'
          branch 'qa'
        }
      }
      agent {
        docker {
          image 'docker:25-cli'
          args '-u root -v /var/run/docker.sock:/var/run/docker.sock --cpus=1'
        }
      }
      steps {
        withCredentials([
          usernamePassword(
            credentialsId: 'dockerhub-creds',
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          ),
          string(
            credentialsId: 'COSIGN_PASSWORD',
            variable: 'COSIGN_PASSWORD'
          ),
          file(
            credentialsId: 'COSIGN_KEY',
            variable: 'COSIGN_KEY'
          )
        ]) {

          sh '''
            set -e
            export HOME=/tmp
            export DOCKER_BUILDKIT=1

            apk add --no-cache curl jq

            curl -sSL https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 \
              -o /usr/local/bin/cosign
            chmod +x /usr/local/bin/cosign

            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            docker buildx create \
              --name "${BUILDER}" \
              --driver docker-container \
              --driver-opt network=host \
              --use 2>/dev/null \
              || docker buildx use "${BUILDER}"

            docker buildx inspect --bootstrap

            docker buildx build \
              --sbom=true \
              --provenance=mode=max \
              --platform linux/amd64 \
              --pull \
              --push \
              --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
              --build-arg GIT_SHA="${GIT_COMMIT}" \
              --build-arg VERSION="${VERSION}" \
              -t "${FULL_IMAGE_VERSION}" \
              -t "${FULL_IMAGE}:latest" \
              .

            DIGEST=$(docker buildx imagetools inspect "${FULL_IMAGE_VERSION}" \
              --format '{{json .Manifest}}' | jq -r '.digest')

            echo "IMAGE DIGEST: ${FULL_IMAGE}@${DIGEST}"

            # curl -sSL https://raw.githubusercontent.com/sigstore/root-signing/refs/heads/main/targets/signing_config.v0.2.json \
            #  | jq 'del(.rekorTlogUrls)' > /tmp/signing_config.json

            echo '{"mediaType":"application/vnd.dev.sigstore.signingconfig.v0.2+json"}' > /tmp/signing_config.json

            export COSIGN_PASSWORD="${COSIGN_PASSWORD}"
            cosign sign \
              --key "${COSIGN_KEY}" \
              --signing-config /tmp/signing_config.json \
              "${FULL_IMAGE_VERSION}@${DIGEST}"

            rm -f "${COSIGN_KEY}" /tmp/signing_config.json
            docker buildx rm "${BUILDER}" || true
            docker logout
          '''
        }
      }
    }

    stage('Docker Image Vulnerability Scan') {
      options { timeout(time: 1, unit: 'HOURS') }
      when {
        anyOf {
          branch 'dev'
          branch 'qa'
        }
      }

      agent {
        docker {
          image 'aquasec/trivy:0.69.3'
          args '-u root --entrypoint="" -v /var/run/docker.sock:/var/run/docker.sock --cpus=1'
        }
      }

      steps {
        withCredentials([usernamePassword(
          credentialsId: 'dockerhub-creds', 
          usernameVariable: 'DOCKER_USER',
          passwordVariable: 'DOCKER_PASS'
        )]) {
        sh '''
          set -e
          export TRIVY_DISABLE_VEX_NOTICE=true

          apk add --no-cache jq curl

          echo "Scanning Docker image: ${FULL_IMAGE_VERSION}"

          export TRIVY_USERNAME=$DOCKER_USER
          export TRIVY_PASSWORD=$DOCKER_PASS

          trivy image ${FULL_IMAGE_VERSION} \
            --scanners vuln,secret \
            --severity CRITICAL,HIGH,MEDIUM,LOW \
            --format json \
            -o image-scan.json

          if [ ! -f image-scan.json ]; then
            echo "ERROR: Scan failed"
            exit 1
          fi

          TOTAL=$(jq '[.Results[].Vulnerabilities[]?] | length' image-scan.json)
          CRITICAL=$(jq '[.Results[].Vulnerabilities[]? | select(.Severity=="CRITICAL")] | length' image-scan.json)
          HIGH=$(jq '[.Results[].Vulnerabilities[]? | select(.Severity=="HIGH")] | length' image-scan.json)
          MEDIUM=$(jq '[.Results[].Vulnerabilities[]? | select(.Severity=="MEDIUM")] | length' image-scan.json)
          LOW=$(jq '[.Results[].Vulnerabilities[]? | select(.Severity=="LOW")] | length' image-scan.json)

          echo "Total: $TOTAL"
          echo "Critical: $CRITICAL"
          echo "High: $HIGH"
          echo "Medium: $MEDIUM"
          echo "Low: $LOW"

          case "$BRANCH_NAME" in
            dev)
              ENVIRONMENT="dev"
              ENGAGEMENT="54"
              ;;
            qa)
              ENVIRONMENT="qa"
              ENGAGEMENT="55"
              ;;
            *)
              ENVIRONMENT="dev"
              ENGAGEMENT="54"
              ;;
          esac

          echo "Uploading image scan to DefectDojo..."

          curl -s -X POST "$DEFECTDOJO_URL/api/v2/import-scan/" \
            -H "Authorization: Token $DEFECTDOJO_TOKEN" \
            -F "scan_type=Trivy Scan" \
            -F "file=@image-scan.json" \
            -F "engagement=$ENGAGEMENT" \
            -F "environment=$ENVIRONMENT" \
            -F "active=true" \
            -F "verified=true" \
            -F "close_old_findings=true"

          echo "Docker image vulnerability scan completed."
        '''
        }
      }

      post {
        always {
          archiveArtifacts artifacts: 'image-scan.json', fingerprint: true, allowEmptyArchive: true
        }
      }
    }
    stage('Deploy to Server') {
      when {
        anyOf {
          branch 'dev'
        }
      }

      agent {
        docker {
          image 'alpine:3.20'
          args '-u root --cpus=1'
        }
      }

      steps {
        script {
            if (env.BRANCH_NAME == 'dev') {
              withCredentials([usernamePassword(
                  credentialsId: 'dockerhub-creds', 
                  usernameVariable: 'DOCKER_USER',
                  passwordVariable: 'DOCKER_PASS'
                )]) {
              sh '''
                  set -e

                  echo "Installing dependencies..."
                  apk add --no-cache sshpass openssh-client

                  echo "Deploying to server..."

                  sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP_DEV << EOF

                  set -e

                  echo "Connected to server"
    
                  cd infra-services

                  # fail if empty
                  [ -z "$SERVICE_DEV" ] && echo "SERVICE_DEV is empty" && exit 1

                  echo "Deploying service: $SERVICE_DEV"

                  echo "Stopping ONLY target service..."

                  docker compose down "$SERVICE_DEV" || {
                    echo "Service not found: $SERVICE_DEV"
                    exit 1
                    }

                  echo "Getting current image for $SERVICE_DEV..."
                  CURRENT_IMAGE=\$(docker compose config | awk '/$SERVICE_DEV:/,/image:/ { if (\$1=="image:") print \$2 }')

                  echo "OLD IMAGE: \$CURRENT_IMAGE"

                  echo "Removing ONLY old image..."
                  if [ -n "\$CURRENT_IMAGE" ]; then
                    docker rmi \$CURRENT_IMAGE || true
                  else
                    echo "No old image found, skipping..."
                  fi

                  echo "Updating ONLY $SERVICE_DEV image..."

                  sed -i "/^  $SERVICE_DEV:/,/image:/ s|image: .*|image: ${FULL_IMAGE_VERSION}|" docker-compose.yml

                  echo "New image for $SERVICE_DEV:"
                  docker compose config | grep -A2 "$SERVICE_DEV"

                  echo "Logging into Docker registry..."
                  echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

                  echo "Running service..."
                  chmod +x run.sh
                  ./run.sh $SERVICE_DEV
              '''
              }
            }
              else if (env.BRANCH_NAME == 'qa') {
                withCredentials([
                  sshUserPrivateKey(
                    credentialsId: 'qa-server-key',
                    keyFileVariable: 'SSH_KEY',
                    passphraseVariable: 'SSH_PASSPHRASE',
                    usernameVariable: 'SSH_USER'
                  )
                ]) {
                sh '''
                    set -e

                    echo "Installing dependencies..."
                    apk add --no-cache openssh-client

                    echo "Starting SSH agent..."
                    eval $(ssh-agent -s)

                    echo "$SSH_PASSPHRASE" | ssh-add "$SSH_KEY"

                    echo "Connecting to server..."

                    ssh -o StrictHostKeyChecking=no $SSH_USER@$SERVER_IP << EOF

                    set -e

                    echo "Connected to server"
            
                    cd infra-service

                    echo "Deploying service: $SERVICE"

                    echo "Stopping ONLY target service..."

                    docker compose down $SERVICE || true

                    echo "Getting current image for $SERVICE..."
                    CURRENT_IMAGE=\$(docker compose config | awk '/$SERVICE:/,/image:/ { if (\$1=="image:") print \$2 }')

                    echo "OLD IMAGE: \$CURRENT_IMAGE"

                    echo "Removing ONLY old image..."
                    if [ -n "\$CURRENT_IMAGE" ]; then
                      docker rmi \$CURRENT_IMAGE || true
                    else
                      echo "No old image found, skipping..."
                    fi

                    echo "Updating ONLY $SERVICE image..."

                    sed -i "/^  $SERVICE:/,/image:/ s|image: .*|image: ${FULL_IMAGE_VERSION}|" docker-compose.yml

                    echo "New image for $SERVICE:"
                    docker compose config | grep -A2 "$SERVICE"

                    echo "Running service..."
                    chmod +x run.sh
                    ./run.sh $SERVICE
               '''
              }
            }
          }
      }
    }
  }

  post {
    always {
        sh 'docker rmi ${FULL_IMAGE} || true'
        sh '''
          echo "Cleaning Jenkins docker garbage..."

          docker ps -aq --filter "label=jenkins" | xargs -r docker rm -f || true

          docker container prune -f || true
          docker image prune -af || true
          docker volume prune -f || true
          docker builder prune -af || true

          docker buildx rm ${BUILDER} || true
        '''

        sh 'docker rmi ${FULL_IMAGE_VERSION} || true'
        sh 'docker rmi ${FULL_IMAGE}:latest || true'

        script {

          env.TRIGGERED_BY = sh(
            script: "git log -1 --pretty=format:'%an' || echo Unknown",
            returnStdout: true
          ).trim()
        
          def status = currentBuild.currentResult
          def color = status == "SUCCESS" ? "Good" : "Attention"
          def emoji = status == "SUCCESS" ? "✅" : "🚨"

          def timestamp = sh(
            script: 'TZ="Asia/Kolkata" date +"%Y-%m-%d %I:%M:%S %p IST"',
            returnStdout: true
          ).trim()

          sh """
            curl -H "Content-Type: application/json" \\
                -d '{
                      "type": "message",
                      "attachments": [{
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                          "\$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                          "type": "AdaptiveCard",
                          "version": "1.4",
                          "body": [{
                            "type": "TextBlock",
                            "text": "${emoji} Build & Deploy- ${status}",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "${color}"
                          },
                            {
                              "type": "FactSet",
                              "facts": [
                                { "title": "Job:", "value": "${env.JOB_NAME}" },
                                { "title": "Build #:", "value": "${env.BUILD_NUMBER}" },
                                { "title": "Image:", "value": "${FULL_IMAGE}" },
                                { "title": "Triggered By:", "value": "${env.TRIGGERED_BY}" },
                                { "title": "Branch:", "value": "${env.BRANCH_NAME}" },
                                { "title": "Repository:", "value": "${env.GIT_URL}" },
                                { "title": "Completed At:", "value": "${timestamp}" }
                                  ]
                            }
                          ],
                          "actions": [{
                            "type": "Action.OpenUrl",
                            "title": "View Build",
                            "url": "${env.BUILD_URL}"
                          }]
                        }
                      }]
                    }' \\
                "$TEAMS_WEBHOOK"
          """
        }
    }
  }
}