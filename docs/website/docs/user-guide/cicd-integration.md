# CI/CD Integration

Guide to integrating CodeGreen energy measurements into your CI/CD pipelines.

## Overview

CodeGreen can be integrated into continuous integration pipelines to:
- Track energy consumption trends over time
- Detect energy regressions in pull requests
- Enforce energy budgets for critical functions
- Generate energy reports in CI artifacts

---

## GitHub Actions

### Basic Energy Measurement

```yaml
name: Energy Profiling

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  energy-profile:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install CodeGreen
        run: |
          git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
          cd /tmp/codegreen
          ./install.sh
          echo "/tmp/codegreen/bin" >> $GITHUB_PATH

      - name: Initialize Sensors
        run: sudo codegreen init-sensors

      - name: Measure Energy
        run: |
          codegreen measure python tests/benchmark.py \
            -g fine \
            --output results/energy.json \
            --json

      - name: Upload Energy Report
        uses: actions/upload-artifact@v3
        with:
          name: energy-report
          path: results/energy.json
```

### Energy Regression Detection

```yaml
name: Energy Regression Check

on:
  pull_request:
    branches: [ main ]

jobs:
  energy-regression:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install CodeGreen
        run: |
          # ... installation steps ...

      - name: Measure PR Energy
        run: |
          codegreen measure python src/main.py \
            --output pr-energy.json --json

      - name: Checkout Main Branch
        run: |
          git fetch origin main
          git checkout main

      - name: Measure Main Energy
        run: |
          codegreen measure python src/main.py \
            --output main-energy.json --json

      - name: Compare Energy
        run: |
          python3 scripts/compare_energy.py \
            main-energy.json pr-energy.json \
            --threshold 10
```

**Energy Comparison Script** (`scripts/compare_energy.py`):
```python
import json, sys

def get_energy(path):
    data = json.load(open(path))
    cps = data.get("measurement", {}).get("checkpoints", [])
    if len(cps) >= 2:
        return cps[-1]["joules"] - cps[0]["joules"]
    return 0.0

def compare_energy(main_file, pr_file, threshold):
    main_e = get_energy(main_file)
    pr_e = get_energy(pr_file)
    change = ((pr_e - main_e) / main_e * 100) if main_e > 0 else 0
    print(f"Main: {main_e:.2f} J | PR: {pr_e:.2f} J | Change: {change:+.1f}%")
    if change > threshold:
        print(f"Energy regression: {change:.1f}% > {threshold}%")
        sys.exit(1)

if __name__ == "__main__":
    compare_energy(sys.argv[1], sys.argv[2], float(sys.argv[3]))
```

### Matrix Testing Across Hardware

```yaml
name: Multi-Platform Energy Testing

on: [push]

jobs:
  energy-test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, ubuntu-22.04]
        granularity: [coarse, fine]

    steps:
      - uses: actions/checkout@v3

      - name: Install CodeGreen
        run: ./scripts/install_codegreen.sh

      - name: Run Energy Tests
        run: |
          codegreen measure python tests/suite.py \
            -g ${{ matrix.granularity }} \
            -o energy-${{ matrix.os }}-${{ matrix.granularity }}.json \
            --json

      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: energy-results-${{ matrix.os }}-${{ matrix.granularity }}
          path: energy-*.json
```

---

## GitLab CI

### Basic Pipeline

```yaml
# .gitlab-ci.yml

stages:
  - setup
  - measure
  - report

install_codegreen:
  stage: setup
  script:
    - git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
    - cd /tmp/codegreen && ./install.sh
  artifacts:
    paths:
      - /tmp/codegreen/bin/codegreen
    expire_in: 1 hour

measure_energy:
  stage: measure
  dependencies:
    - install_codegreen
  script:
    - export PATH="/tmp/codegreen/bin:$PATH"
    - sudo codegreen init-sensors
    - codegreen measure python app/main.py --output energy.json --json
  artifacts:
    reports:
      metrics: energy.json
    paths:
      - energy.json
    expire_in: 30 days

generate_report:
  stage: report
  dependencies:
    - measure_energy
  script:
    - python3 scripts/generate_energy_report.py energy.json > report.md
  artifacts:
    paths:
      - report.md
    expire_in: 30 days
```

### Merge Request Energy Check

```yaml
energy_mr_check:
  stage: measure
  only:
    - merge_requests
  script:
    - export PATH="/tmp/codegreen/bin:$PATH"
    - sudo codegreen init-sensors

    # Measure MR branch
    - codegreen measure python app/main.py --output mr_energy.json --json

    # Fetch and measure target branch
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
    - git checkout $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
    - codegreen measure python app/main.py --output target_energy.json --json

    # Compare
    - python3 scripts/compare_energy.py target_energy.json mr_energy.json --threshold 15
  allow_failure: true
```

---

## Jenkins Pipeline

### Declarative Pipeline

```groovy
pipeline {
    agent any

    stages {
        stage('Install CodeGreen') {
            steps {
                sh '''
                    git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
                    cd /tmp/codegreen
                    ./install.sh
                '''
            }
        }

        stage('Initialize Sensors') {
            steps {
                sh 'sudo /tmp/codegreen/bin/codegreen init-sensors'
            }
        }

        stage('Energy Measurement') {
            steps {
                sh '''
                    export PATH="/tmp/codegreen/bin:$PATH"
                    codegreen measure python src/application.py \
                        -g fine \
                        --output energy-${BUILD_NUMBER}.json \
                        --json
                '''
            }
        }

        stage('Archive Results') {
            steps {
                archiveArtifacts artifacts: 'energy-*.json', fingerprint: true
            }
        }

        stage('Trend Analysis') {
            steps {
                sh '''
                    python3 -c "
import json
data = json.load(open('energy-${BUILD_NUMBER}.json'))
cps = data.get('measurement', {}).get('checkpoints', [])
if len(cps) >= 2:
    energy = cps[-1]['joules'] - cps[0]['joules']
    print(f'Total Energy: {energy:.2f} J')
"
                '''
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
```

---

## Docker Integration

### Dockerfile for CI

```dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libjsoncpp-dev \
    libcurl4-openssl-dev \
    libsqlite3-dev \
    python3 \
    python3-pip \
    git

# Install CodeGreen
RUN git clone https://github.com/SMART-Dal/codegreen.git /opt/codegreen && \
    cd /opt/codegreen && \
    ./install.sh

ENV PATH="/opt/codegreen/bin:${PATH}"

# Initialize sensors (requires privileged mode)
# Note: Run container with --privileged flag
RUN codegreen doctor

WORKDIR /workspace
```

### Docker Compose for CI

```yaml
version: '3.8'

services:
  codegreen-ci:
    build:
      context: .
      dockerfile: Dockerfile.codegreen
    privileged: true
    volumes:
      - ./src:/workspace/src
      - ./results:/workspace/results
    command: |
      bash -c "
        sudo codegreen init-sensors &&
        codegreen measure python /workspace/src/main.py \
          --output /workspace/results/energy.json \
          --json
      "
```

**Run:**
```bash
docker-compose run codegreen-ci
```

---

## Travis CI

```yaml
# .travis.yml

language: python
python:
  - "3.9"

before_install:
  - git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
  - cd /tmp/codegreen && ./install.sh
  - export PATH="/tmp/codegreen/bin:$PATH"

install:
  - pip install -r requirements.txt

before_script:
  - sudo codegreen init-sensors

script:
  - codegreen measure python tests/benchmark.py --output energy.json --json

after_success:
  - python scripts/upload_energy_metrics.py energy.json
```

---

## CircleCI

```yaml
# .circleci/config.yml

version: 2.1

jobs:
  energy-measurement:
    docker:
      - image: ubuntu:22.04
    steps:
      - checkout

      - run:
          name: Install CodeGreen
          command: |
            apt-get update
            apt-get install -y git build-essential cmake python3
            git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
            cd /tmp/codegreen && ./install.sh
            echo 'export PATH="/tmp/codegreen/bin:$PATH"' >> $BASH_ENV

      - run:
          name: Initialize Sensors
          command: codegreen init-sensors

      - run:
          name: Measure Energy
          command: |
            codegreen measure python app/main.py \
              --output /tmp/energy.json \
              --json

      - store_artifacts:
          path: /tmp/energy.json
          destination: energy-report

workflows:
  version: 2
  energy-workflow:
    jobs:
      - energy-measurement
```

---

## Best Practices

### 1. Sensor Initialization

Always initialize sensors before measurements:
```bash
sudo codegreen init-sensors
# OR
sudo codegreen init-sensors
```

### 2. Consistent Hardware

Run energy measurements on consistent hardware:
- Use dedicated CI runners with RAPL support
- Pin to specific runner tags
- Document hardware specifications

```yaml
# GitHub Actions
runs-on: [self-hosted, energy-capable]

# GitLab CI
tags:
  - energy-capable
  - ubuntu
```

### 3. Baseline Measurements

Establish energy baselines:
```bash
# Store baseline
codegreen measure python tests/baseline.py --output baseline.json

# Compare against baseline
python scripts/compare_energy.py baseline.json current.json
```

### 4. Energy Budgets

Set per-function energy budgets:
```python
# energy_budget.json
{
  "compute_transform": {"max_joules": 10.0},
  "process_data": {"max_joules": 5.0},
  "render_output": {"max_joules": 2.0}
}
```

```bash
codegreen measure python app.py --output results.json
python scripts/check_budget.py results.json energy_budget.json
```

### 5. Artifact Management

Archive energy reports for historical tracking:
```yaml
# GitHub Actions
- uses: actions/upload-artifact@v3
  with:
    name: energy-report-${{ github.sha }}
    path: energy.json
    retention-days: 90
```

---

## Troubleshooting CI

### Permission Denied (RAPL)

**Problem:** CI runner can't access `/sys/class/powercap/`

**Solution 1 - Persistent Permissions:**
```bash
# Add to runner setup script
sudo chmod -R 644 /sys/class/powercap/intel-rapl:*/energy_uj
```

**Solution 2 - Init Sensors:**
```bash
sudo codegreen init-sensors
```

### Docker Privileged Mode

**Problem:** Docker container can't access hardware sensors

**Solution:**
```yaml
services:
  ci:
    image: ubuntu:22.04
    privileged: true  # Required for RAPL access
```

### Inconsistent Results

**Problem:** Energy measurements vary widely between runs

**Solutions:**
1. Increase measurement duration
2. Use multiple runs and average
3. Run on dedicated hardware
4. Set CPU frequency scaling to performance mode

```bash
# Set performance mode
sudo cpupower frequency-set --governor performance

# Run multiple times
for i in {1..5}; do
  codegreen measure python app.py --output run-$i.json
done

# Average results
python scripts/average_energy.py run-*.json
```

---

## Example: Complete GitHub Actions Workflow

```yaml
name: Energy CI/CD

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  energy-check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install CodeGreen
        run: |
          git clone https://github.com/SMART-Dal/codegreen.git /tmp/codegreen
          cd /tmp/codegreen && ./install.sh
          echo "/tmp/codegreen/bin" >> $GITHUB_PATH

      - name: Initialize Sensors
        run: sudo codegreen init-sensors

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Run Energy Measurements
        run: |
          mkdir -p results
          codegreen measure python tests/benchmark.py \
            -g fine \
            --output results/energy.json \
            --json

      - name: Check Energy Budget
        run: |
          python scripts/check_budget.py \
            results/energy.json \
            config/energy_budget.json

      - name: Generate Report
        run: |
          python scripts/generate_report.py \
            results/energy.json \
            > results/report.md

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('results/report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });

      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: energy-results
          path: results/
```

---

## See Also

- [CLI Reference](cli-reference.md) - Complete command reference
- [Configuration Reference](configuration-reference.md) - Complete configuration guide
- [Examples](../examples/python.md) - Usage examples
