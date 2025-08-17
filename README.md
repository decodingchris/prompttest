# prompttest

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

pytest for LLMs.

You wouldn't ship code without tests. ✋😮🤚

Hold your prompts to the same standard. 😎👌🔥

## Features

- **🔤 Test in Plain English:** Use an AI judge to test your prompts against criteria written in plain English.
- **🚀 Write Tests Faster:** Define your test cases in simple YAML—no test functions, no boilerplate, just your data.
- **🔓 Avoid Vendor Lock-in:** Test your prompts against current and future LLMs through a single, free OpenRouter API key.

## Quick Start

### 1. Install prompttest

```bash
pip install prompttest
```

### 2. Set up prompttest

```bash
prompttest init
```

### 3. Run your tests

```bash
prompttest
```

## How It Works

prompttest is built around 3 simple file types:

-   **Prompt:** Your prompt template with `{variables}`.

-   **Test:** Your test cases, with `inputs` and the `criteria` for a good response.

-   **Config:** Your `config` for default models and `reusable` test values.

## Contributing

We're building the pytest for LLMs, and we need your help.

As an early project, your contributions—from bug reports and feature ideas to code—have a massive impact.

Help shape a foundational tool for the next wave of AI development.

## License

This project is licensed under the MIT License.
