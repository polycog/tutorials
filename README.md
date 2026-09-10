# `cognition` Smart Home Tutorial Series

Welcome to the tutorial series for the **`cognition`** library. This repository contains step-by-step guides, interactive Jupyter Notebooks, and complete Python reference implementations.
---

## 📌 Overview

**`cognition`** is a neurosymbolic agent framework that combines probabilistic neural processing with deterministic, symbolic, logical reasoning. It is designed for building trustworthy agents that are reliable, steerable, and explainable.`cognition` brings together frontier models and deterministic, symbolic AI.

`cognition` builds upon the classic **Perceive–Decide–Act** agentic loop and provides methods to program intelligent behaviors.

---

## 🤖 What You'll Build
Imagine managing a dynamic, multi-room environment where natural language user requests (*"which device in my kitchen is running, turn the dishawasher off"*) must translate into reliable, safe, and context-aware device actions.

Throughout this tutorial series, you will build a Smart Home Assistant from the ground up. You'll start with fundamental state transitions and progress to building a neurosymbolic agent capable of parsing unstructured intent, maintaining a graph representation of room topologies, and executing multi-step tasks.

https://github.com/user-attachments/assets/ac8bc86f-1e29-44c8-9b96-ef45a08f08c2

> Demo Preview: The video above showcases the final agent interpreting natural language requests, querying its internal world graph for relationships, and issuing real-time API commands to devices across a simulated smart home.

---

## 📚 Tutorial Roadmap

This repository is organized into four sequential tutorials that guide you from core concepts to advanced agent architectures:

### ⚙️ Tutorial 1: Decision Processes
* **Agentic AI Concept**: *Orchestration* - co-ordinating and controlling steps in a task.  
* **Core Constructs**: `DecisionProcess`, `State`, `Operator`, termination check
* **Key Focus**: Building deterministic decision processes using `Operator` classes with explicit guard conditions (`can_perform`) and handlers (`perform`). Learn how operators inspect and update internal `State` and how terminal checks conclude the process.

### 🤖 Tutorial 2: Cogents (Cognitive Agents)
* **Agentic AI Concept**: *Agent Harness/Runtime* - driving agent operational loop and handling I/O with the environment.
* **Core Constructs**: `Cogent`, `Sensor`, `Actuator`, Perceive–Decide–Act Loop, `IOContainer`
* **Key Focus**: Wrapping a decision process into a `Cogent` instance. Learn how to interface an agent with external environments by creating strongly typed `Sensor` (telemetry ingestion) and `Actuator` (command dispatch) components.

### 💬 Tutorial 3: Human-Cogent Communication
* **Agentic AI Concept**: *Language Model* - understanding what the human is asking for by mapping unstructured natural language to structured state representation and API calls.
* **Core Constructs**: `AutoDocEnum`, `EnumClassifier`, Utterance vs Intent, Separation of Intent Interpretation and Execution
* **Key Focus**: Connecting conversational interfaces (Chat UIs) to an agent. Convert raw, unstructured text into strongly typed enum intents using `EnumClassifier` (built on `pydantic_ai`). Enforce a whitelist security architecture and implement explicit fallback handling for unmapped user inputs.

### 🏗️ Tutorial 4: Hierarchical Decision Processes
* **Agentic AI Concept**: *Multi-Agent* - organizing a task into several sub-tasks. 
* **Core Constructs**: Nested `DecisionProcess`
* **Key Focus**: Scaling agents to complex tasks. Learn how to nest child `DecisionProcess` instances inside parent `Operator` classes to decompose complex tasks (e.g., two-stage verb/noun intent parsing) into modular, isolated sub-loops.

### 🌐 Tutorial 5: World Model
* **Agentic AI Concept**: *Reasoning* - generating a response via grounding with a graph 
* **Core Constructs**: `WorldGraph`, `describe_facts`, Relational State Representation, Graph Topology, Graph-based Reasoning
* **Key Focus**: Extending state management with graph-based world models. Learn how to construct, query, and dynamically update a `WorldGraph` representing multi-room topology, entity connections, and device hierarchies. Utilize the `describe_facts` function to serialize graph triples and relational knowledge into structured text prompts, enabling grounded response generatior.

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
├── 01_decision_processes.ipynb             # Tutorial 1: State, Operators, & Decision Process mechanics
├── 02_cogents.ipynb                        # Tutorial 2: Sensors, Actuators, & Perceive-Decide-Act loops
├── 03_human_cogent_communication.ipynb     # Tutorial 3: Chat UIs, NLU enums, & Intent parsing
├── 04_hierarchical_decision_processes.ipynb# Tutorial 4: Nested sub-processes & multi-room state
├── 05_world_graphs.ipynb                   # Tutorial 5: World graph modeling, describe_facts & spatial reasoning
├── smart_home_assistant_v1.py                      # Tutorial 1: Basic deterministic device control script
├── smart_home_assistant_v2.py                      # Tutorial 2: Full Cogent integration with I/O containers script
├── smart_home_assistant_v3.py                      # Tutorial 3: Chat interface & NLU classifier script
├── smart_home_assistant_v4.py                      # Tutorial 4: Production-ready hierarchical agent script
├── smart_home_assistant_v5.py                      # Tutorial 5: World graph & describe_facts agent script
├── utils.py                                        # Cogent runtime loop driver & error suppression policies
└── smart_home/                                     # Smart Home Simulation Package
    ├── smart_home.py                               # Simulation server (supports default `simple` and `--mode realistic`)
    └── client.py                                   # Socket API client interface (`SmartHomeClient`)
```

---

## 🚀 Quickstart Guide

### 0. Install Requirements

In addition to the `cognition` library, you'll need to install packages for the tutorial smart home and language models in your preferred Python (virtual) environment.
To start:

```bash
pip install -r smart_home/requirements.txt
```

Tutorials 3-4 make use of language models - the Polycog library makes use of Pydantic AI to abstract API access, but requires that you then install the appropriate group for your preferred provider. See [Pydantic docs](https://pydantic.dev/docs/ai/models/overview/) for details, but the install for OpenAI would then require...

```bash
pip install "pydantic-ai-slim[openai]"
```

### 1. Set Up Environment Variables

Tutorials 3-4 make use of language models; by default we've assumed an cloud-based OpenAI model (`gpt-4o`) - if this works with your setup, be sure to make the key is available within your execution environment:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

If you prefer a different model or provider (including a local server), feel free to adjust the supplied code (and environmental variable) to your needs. See [Pydantic docs](https://pydantic.dev/docs/ai/models/overview/) for details.

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
