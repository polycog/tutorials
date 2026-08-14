# `cognition` Smart Home Tutorial Series

Welcome to the tutorial series for the **`cognition`** library. This repository contains step-by-step guides, interactive Jupyter Notebooks, and complete Python reference implementations for building trustworthy AI agents.

---

## 📌 Overview

**`cognition`** is a neurosymbolic agent framework that combines probabilistic neural processing with deterministic, symbolic, logical reasoning. It is designed for building trustworthy agents that are reliable, steerable, and explainable.`cognition` brings together frontier models and deterministic, symbolic AI.

`cognition` builds upon the classic **Perceive–Decide–Act** agentic loop and provides methods to program intelligent behaviors.

---

## 📚 Tutorial Roadmap

This repository is organized into four sequential tutorials that guide you from core state-machine concepts to advanced multi-level agent architectures:

### ⚙️ Tutorial 1: Decision Processes
* **Core Concepts**: `DecisionProcess`, `State`, `Operator`, terminaton check,
* **Key Focus**: Building deterministic decision processes using `Operator` classes with explicit guard conditions (`can_perform`) and handlers (`perform`). Learn how operators inspect and update internal `State`.

### 🤖 Tutorial 2: Cogents
* **Core Concepts**: `Cogent`, `Sensor`, `Actuator`, Perceive–Decide–Act Loop, `IOContainer`
* **Key Focus**: Wrapping a decision process into a `Cogent` instance. Learn how to interface an agent with external environments by creating strongly typed `Sensor` (telemetry ingestion) and `Actuator` (command dispatch) components.

### 💬 Tutorial 3: Human-Cogent Communication
* **Core Concepts**: `Utterance`, `AutoDocEnum`, `EnumClassifier`, Separation of Intent Interpretation and Exacution.
* **Key Focus**: Connecting conversational interfaces (Chat UIs) to an agent. Convert raw, unstructured text into strongly typed enum intents using `EnumClassifier` (built on `pydantic_ai`). Enforce a whitelist security architecture and implement explicit fallback handling for unmapped user inputs.

### 🏗️ Tutorial 4: Hierarchical Decision Processes
* **Core Concepts**: Nested `DecisionProcess`.
* **Key Focus**: Scaling agents to complex tasks. Learn how to nest child `DecisionProcess` instances inside parent `Operator` classes to decompose complex tasks (e.g., two-stage verb/noun intent parsing) into modular, isolated sub-loops.

---

## 🏡 The Smart Home Simulation Environment

The smart home simulation server runs as an external service that your agent connects to via Flask RESTful APIs. It can be executed in two different modes depending on the tutorial complexity:

* **`simple` mode** *(Default)*: A lightweight, single-device environment featuring a single light fixture and chat window. Used for basic concepts in Tutorials 1–3. You can run it without any flags or explicitly pass `--mode simple`:
  ```bash
  # Run default simple mode
  python smart_home/smart_home.py

  # Or explicitly specify simple mode
  python smart_home/smart_home.py --mode simple
  ```

* **`realistic` mode**: A full multi-room, multi-device environment featuring 9 devices across 5 rooms with varied operational states. Used for Tutorial 4 (Hierarchical Decision Processes):
  ```bash
  python smart_home/smart_home.py --mode realistic
  ```

---

## 📁 Repository Directory Structure

```
.
├── README.md                                       # Main repository documentation
├── tutorial_1_decision_processes.ipynb             # Tutorial 1: State, Operators, & Decision Process mechanics
├── tutorial_2_cogents.ipynb                        # Tutorial 2: Sensors, Actuators, & Perceive-Decide-Act loops
├── tutorial_3_human_cogent_communication.ipynb     # Tutorial 3: Chat UIs, NLU enums, & Intent parsing
├── tutorial_4_hierarchical_decision_processes.ipynb# Tutorial 4: Nested sub-processes & multi-room state
├── smart_home_assistant_v1.py                      # Tutorial 1: Basic deterministic device control script
├── smart_home_assistant_v2.py                      # Tutorial 2: Full Cogent integration with I/O containers script
├── smart_home_assistant_v3.py                      # Tutorial 3: Chat interface & NLU classifier script
├── smart_home_assistant_v4.py                      # Tutorial 4: Production-ready hierarchical agent script
├── utils.py                                        # Cogent runtime loop driver & error suppression policies
└── smart_home/                                     # Smart Home Simulation Package
    ├── smart_home.py                               # Simulation server (supports default `simple` and `--mode realistic`)
    └── client.py                                   # Socket API client interface (`SmartHomeClient`)
```

---

## 🚀 Quickstart Guide

### 1. Set Up Environment Variables

Set your OpenAI API key required for LLM classification components (`EnumClassifier`):

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 2. Start the Simulation (Terminal 1)

For Tutorials 1–3:
```bash
python smart_home/smart_home.py
```

For Tutorial 4:
```bash
python smart_home/smart_home.py --mode realistic
```

### 3. Run the Agent or Notebook (Terminal 2)

Execute a standalone Python implementation:
```bash
python smart_home_assistant_v4.py
```

Or open the interactive Jupyter tutorials:
```bash
jupyter notebook tutorial_4_hierarchical_decision_processes.ipynb
```
