# C++ Agent dev team experiment

This repository hosts an agent-based development framework designed to facilitate the automated creation of C++ applications using the openai api and LangGraph (https://langchain-ai.github.io/langgraph/). The framework employs a series of specialized agents, each fulfilling a critical role in the development lifecycle, managed through a develop-test-debug loop to ensure robust, efficient, and modular software development.

## Features

- Modular agent roles for streamlined development cycles.
- Customizable prompts to adapt the workflow to any C++ application.
- Automated develop-test-debug loop for continuous integration and delivery.

## Agent Roles and Development Cycle

### Planner
The Planner agent breaks down the high-level application description into a detailed development roadmap. It assigns specific implementation tasks to developers, ensuring that each task is modular and can be independently tested. The planner continuously updates the development roadmap based on the progress and feedback from other agents.

### Main Developer
Responsible for the actual coding of the application as per the planner's instructions. This developer focuses on specific modules, keeping in mind the overall architecture and end goals of the application. Each piece of code provided must be accompanied by a corresponding unit test to ensure functionality.

### Unit Tester
This agent creates and runs unit tests for newly developed modules to ensure they function correctly as per the specifications. The results are then communicated back to the planner and the main developer for further action.

### Debugger
Tasked with analyzing and rectifying issues highlighted by failed unit tests. This agent devises strategies to correct the code or to further diagnose problems, ensuring the stability and reliability of the application.

### Researcher
Supports the development team by providing necessary documentation and information. This agent generates search queries to find specific C++ documentation and other resources needed for the implementation of tasks.

### Feedback Provider
Reviews the implemented code for potential improvements in performance, robustness, and thread safety. This agent ensures that the functionality of each module integrates well within the overall application.

## Customizable Prompts

Each agent operates based on customizable prompts that define their tasks and responsibilities. These prompts are structured to be easily modified, allowing the development team to adapt the framework to various C++ applications with different requirements and goals. By changing these prompts, teams can tailor the development process to align with specific technical specifications, frameworks, and architectural needs.

## Develop-Test-Debug Loop

The interaction between the agents creates a continuous loop of development, testing, and debugging, which facilitates rapid and reliable software development. This loop ensures that:
- Each module is developed with a clear understanding of its role within the larger application.
- All code is thoroughly tested, ensuring functionality and robustness.
- Any arising issues are promptly addressed, minimizing disruptions in the development process.

## Getting Started

To use this framework:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/yourrepository.git
   cd yourrepository

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or later
- Necessary Python packages, which can be installed via pip:
  ```bash
  pip install -r requirements.txt


## Run

When you edited the prompts.py with descriptions of your application and requirements, start the development process by running the agents_dev_team.py script.

